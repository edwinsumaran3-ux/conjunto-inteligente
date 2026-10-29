import asyncio
import json
import logging
import os
import re
import uuid

import aio_pika
import asyncpg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from fastapi.responses import Response

from agent_loop import AgentOrchestratorLoop
from agents.hardware_integrity_agent import HardwareIntegrityAgent
from agents.intrusion_agent import IntrusionAgent
from agents.perimeter_agent import PerimeterAgent
from chain_communicator import ChainCommunicator
from human_validation import HumanValidationGate
from models import ApprovalDecisionIn, Incident
from security_headers import SecurityHeadersMiddleware
from correlation_id import CorrelationIdMiddleware
from equipment_registry import EquipmentRegistry
from equipment_adapters.drone_adapter_boundary import DroneAdapterBoundary
from equipment_adapters.ptz_camera_adapter_boundary import PtzCameraAdapterBoundary
from equipment_adapters.ground_robot_adapter_boundary import GroundRobotAdapterBoundary
from equipment_adapters.ir_actuator_adapter_boundary import IrActuatorAdapterBoundary
from drone_catalog import DRONE_CATALOG, get_model
from operator_auth import require_operator, read_guard
from resilience import process_message
from control.audit import AuditLog
from control.command_journal import CommandJournal

RABBIT_URL = os.getenv("RABBIT_URL", "amqp://vigia:change-me@rabbitmq/")
DB_DSN = os.getenv("DB_DSN", "postgresql://vigia:change-me@postgres:5432/vigilancia")

log = logging.getLogger("agent-orchestrator")
EQUIPMENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,126}$")
app = FastAPI(title="Agent Orchestrator", version="1.0.0")
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","), allow_methods=["GET","POST"], allow_headers=["Content-Type","X-Correlation-ID","X-Operator-Token"])

state: dict = {"pool": None, "loop_engine": None, "conn": None, "tasks": []}

@app.on_event("startup")
async def startup():
    pool = await asyncpg.create_pool(DB_DSN, min_size=2, max_size=10)
    conn = await aio_pika.connect_robust(RABBIT_URL)
    channel = await conn.channel()
    await channel.set_qos(prefetch_count=50)
    incidents_ex = await channel.declare_exchange("incidents.fanout", aio_pika.ExchangeType.FANOUT, durable=True)
    queue = await channel.declare_queue("agent-orchestrator.q", durable=True)
    await queue.bind(incidents_ex)

    chain = ChainCommunicator(channel)
    await chain.start()
    gate = HumanValidationGate(pool)
    agents = [IntrusionAgent(), PerimeterAgent(), HardwareIntegrityAgent()]

    # Registro de equipos físicos con frontera operacional explícita: se
    # admiten por tipo, pero cada adaptador rechaza en frío (fail-closed)
    # hasta que se conecte el transporte real del fabricante. Ver
    # docs/10-fusion-unificacion-plataforma.md.
    journal = CommandJournal(pool)
    await journal.ensure_schema()
    audit = AuditLog(pool)
    equipment = EquipmentRegistry(journal=journal, audit=audit)
    equipment.register(DroneAdapterBoundary("drone-01", get_model("dji-matrice-300-rtk")))
    equipment.register(PtzCameraAdapterBoundary("ptz-01"))
    equipment.register(GroundRobotAdapterBoundary("ground-robot-01"))
    equipment.register(IrActuatorAdapterBoundary("ir-actuator-01"))

    engine = AgentOrchestratorLoop(pool, agents, gate, chain, equipment)

    state.update(pool=pool, conn=conn, gate=gate, engine=engine, equipment=equipment, journal=journal, audit=audit)

    async def handle(msg):
        payload = json.loads(msg.body)
        incident = Incident(**payload)
        await engine.handle_incident(incident)

    async def consume():
        # Política de fallos: mensaje venenoso -> dead_letter_messages (no se reencola sin fin);
        # fallo transitorio -> 1 reintento. Antes `process(requeue=True)` bloqueaba la cola con un JSON inválido.
        async with queue.iterator() as it:
            async for msg in it:
                await process_message(msg, handle, pool=pool, service="agent-orchestrator", queue="agent-orchestrator.q")

    # Se conservan referencias: una tarea sin referencia puede ser recolectada y detenerse en silencio.
    state["tasks"] = [asyncio.create_task(consume(), name="incident-consumer"), asyncio.create_task(engine.run_forever(), name="agent-loop")]

@app.on_event("shutdown")
async def shutdown():
    for t in state.get("tasks", []):
        t.cancel()
    await asyncio.gather(*state.get("tasks", []), return_exceptions=True)
    if state["pool"]:
        await state["pool"].close()
    if state["conn"]:
        await state["conn"].close()

@app.get("/healthz")
async def healthz():
    try:
        await state["pool"].fetchval("SELECT 1")
        dead = [t.get_name() for t in state.get("tasks", []) if t.done()]
        if dead:
            raise RuntimeError(f"background tasks stopped: {dead}")
        return {"status": "ok", "agents": state["engine"].status["agents"]}
    except Exception:
        raise HTTPException(503, "degraded")

@app.get("/agents/status")
async def agents_status():
    return state["engine"].status

@app.get("/approvals/pending")
async def approvals_pending(_: str = Depends(read_guard)):
    return await state["gate"].pending()

@app.get("/approvals/history")
async def approvals_history(limit: int = 50, _: str = Depends(read_guard)):
    limit = max(1, min(limit, 500))
    async with state["pool"].acquire() as c:
        rows = await c.fetch(
            """SELECT a.approval_id,a.action_id,a.decision,a.decided_by,a.decided_at,a.requested_at,a.expires_at,
                      x.agent_name,x.action_type,x.severity,x.target_device_id,x.zone,x.rationale
               FROM agent_approvals a JOIN agent_actions x ON x.action_id=a.action_id
               WHERE a.decision!='PENDING' ORDER BY a.requested_at DESC LIMIT $1""",
            limit,
        )
    return [dict(r) for r in rows]

@app.post("/approvals/{approval_id}/decide")
async def decide(approval_id: str, body: ApprovalDecisionIn, _: str = Depends(require_operator)):
    try:
        uuid.UUID(approval_id)
    except ValueError:
        raise HTTPException(400, "approval_id debe ser un UUID")
    if not body.decided_by.strip() or len(body.decided_by) > 128:
        raise HTTPException(400, "decided_by inválido")
    result = await state["gate"].decide(approval_id, body.decided_by, body.decision, body.operator_signature)
    if not result:
        raise HTTPException(409, "aprobación ya resuelta, vencida o inexistente")
    await state["audit"].record(actor="operator", actor_type="OPERATOR", action=f"APPROVAL_{body.decision}",
                                entity_type="approval", entity_id=approval_id,
                                details={"decided_by_claimed": body.decided_by, "action_id": str(result["action_id"])})
    if body.decision == "APPROVED":
        async with state["pool"].acquire() as c:
            action = await c.fetchrow("SELECT action_id,action_type,target_device_id,zone,payload FROM agent_actions WHERE action_id=$1", result["action_id"])
        try:
            await state["engine"].apply_approved(
                approval_id, str(action["action_id"]), action["action_type"],
                action["target_device_id"], action["zone"], json.loads(action["payload"]) if isinstance(action["payload"], str) else action["payload"],
            )
        except Exception as exc:
            # La decisión humana quedó registrada, pero la ejecución falló: no se debe responder 200 ni dejar
            # la acción en APPROVED como si se hubiera ejecutado.
            log.exception("fallo al ejecutar la acción aprobada %s", result["action_id"])
            async with state["pool"].acquire() as c:
                await c.execute("UPDATE agent_actions SET status='DISPATCH_FAILED' WHERE action_id=$1", result["action_id"])
            await state["audit"].record(actor="agent-orchestrator", actor_type="SYSTEM", action="APPROVED_ACTION_DISPATCH_FAILED",
                                        entity_type="action", entity_id=str(result["action_id"]), details={"error": type(exc).__name__})
            raise HTTPException(502, "decisión registrada pero la ejecución falló; revisar /actions/recent")
    return {"approval_id": approval_id, "decision": body.decision}

@app.get("/actions/recent")
async def actions_recent(limit: int = 100, _: str = Depends(read_guard)):
    limit = max(1, min(limit, 500))
    async with state["pool"].acquire() as c:
        rows = await c.fetch("SELECT action_id,incident_id,agent_name,action_type,severity,target_device_id,zone,rationale,status,created_at,resolved_at FROM agent_actions ORDER BY created_at DESC LIMIT $1", limit)
    return [dict(r) for r in rows]

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/equipment/commands/recent")
async def equipment_commands_recent(limit: int = 100, _: str = Depends(read_guard)):
    limit = max(1, min(limit, 500))
    async with state["pool"].acquire() as c:
        rows = await c.fetch("SELECT command_id,equipment_id,equipment_type,action,issued_by,status,reason,created_at,completed_at FROM equipment_command_journal ORDER BY created_at DESC LIMIT $1", limit)
    return [dict(r) for r in rows]

@app.get("/equipment/registry")
async def equipment_registry(_: str = Depends(read_guard)):
    out = []
    for a in state["equipment"].all():
        t = await a.get_telemetry()
        out.append({"equipment_id": a.equipment_id, "equipment_type": a.equipment_type.value, "is_connected": a.is_connected, "state": t.state, "values": t.values})
    return out

@app.post("/equipment/emergency-stop")
async def equipment_emergency_stop(_: str = Depends(require_operator)):
    results = await state["equipment"].emergency_stop_all()
    failed = {k: v for k, v in results.items() if v != "ok"}
    return {"status": "emergency_stop_issued" if not failed else "emergency_stop_partial", "results": results}

@app.get("/equipment/drone-catalog")
def drone_catalog():
    return [d.__dict__ for d in DRONE_CATALOG]

@app.post("/equipment/drones")
async def register_drone(body: dict, _: str = Depends(require_operator)):
    equipment_id = body.get("equipment_id")
    model_key = body.get("model_key")
    if not equipment_id or not model_key:
        raise HTTPException(400, "equipment_id y model_key requeridos")
    if not isinstance(equipment_id, str) or not EQUIPMENT_ID_RE.match(equipment_id):
        raise HTTPException(400, "equipment_id inválido (alfanumérico, '_', '-', '.'; máx. 127)")
    if not isinstance(model_key, str):
        raise HTTPException(400, "model_key inválido")
    if any(a.equipment_id == equipment_id for a in state["equipment"].all()):
        # Antes un registro repetido reemplazaba en silencio al adaptador existente.
        raise HTTPException(409, "equipment_id ya registrado")
    model = get_model(model_key)
    if not model:
        raise HTTPException(404, "modelo no encontrado en el catálogo")
    state["equipment"].register(DroneAdapterBoundary(equipment_id, model))
    await state["audit"].record(actor="operator", actor_type="OPERATOR", action="EQUIPMENT_REGISTERED",
                                entity_type="equipment", entity_id=equipment_id, details={"model_key": model_key})
    return {"equipment_id": equipment_id, "model": model.model, "vendor": model.vendor, "status": "registered_fail_closed"}
