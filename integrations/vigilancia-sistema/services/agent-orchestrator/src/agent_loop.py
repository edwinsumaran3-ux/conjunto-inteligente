import asyncio
import dataclasses
import json
import logging
import time
import uuid
import os
from prometheus_client import Counter, Gauge
from models import Incident, ActionProposal
from agents.base_agent import BaseAgent
from human_validation import HumanValidationGate
from chain_communicator import ChainCommunicator
from equipment_registry import EquipmentRegistry
from equipment_contracts import EquipmentCommand, EquipmentType
from neural_advisor import NeuralAdvisor
from control.command_security import sign_for_equipment

log = logging.getLogger("agent_loop")

LOOP_ITER = Counter("agent_loop_iterations_total", "Iteraciones del loop de agentes")
PROPOSALS = Counter("agent_proposals_total", "Propuestas de acción", ["agent", "action_type"])
AUTO_EXECUTED = Counter("agent_actions_auto_executed_total", "Acciones auto-ejecutadas (no destructivas)")
PENDING_GAUGE = Gauge("agent_approvals_pending", "Aprobaciones humanas pendientes")
FALLBACK = Counter("agent_approvals_expired_fallback_total", "Aprobaciones vencidas que activaron fallback seguro")
AGENT_ERRORS = Counter("agent_assess_errors_total", "Excepciones de un agente al evaluar un incidente", ["agent"])
LOOP_ERRORS = Counter("agent_loop_errors_total", "Excepciones contenidas en el loop de fondo")
DUPLICATE_PROPOSALS = Counter("agent_duplicate_proposals_skipped_total", "Propuestas omitidas por redelivery del mismo incidente")

class AgentOrchestratorLoop:
    """Ciclo continuo de percepción/planificación/acción/reflexión.

    Sense   -> recibe incidentes ya correlacionados (vía RabbitMQ, en main.py)
    Plan    -> cada agente relevante evalúa el incidente y puede proponer una acción
    Action  -> se persiste la propuesta; si no requiere aprobación se despacha
               de inmediato; si la requiere, entra a la cola de HumanValidationGate
    Reflect -> en cada tick se barren aprobaciones vencidas y se aplica el
               fallback seguro, y se recalcula el estado expuesto en /agents/status
    """

    def __init__(self, pool, agents: list[BaseAgent], gate: HumanValidationGate, chain: ChainCommunicator, equipment: EquipmentRegistry | None = None, tick_s: float = 3.0, neural: NeuralAdvisor | None = None):
        self.pool = pool
        self.agents = agents
        self.gate = gate
        self.chain = chain
        self.equipment = equipment
        self.tick_s = tick_s
        self.neural = neural or NeuralAdvisor()
        self.status: dict = {"agents": [a.name for a in agents], "last_tick": None, "last_incident": None, "pending_approvals": 0}

    async def _dispatch(self, action_id: str, action_type: str, target_device_id: str | None, zone: str | None, payload: dict):
        """Único punto de salida de cualquier acción ya resuelta (auto-aprobada
        o confirmada por un humano). Si `target_device_id` corresponde a un
        equipo dado de alta en `EquipmentRegistry` (dron/PTZ/robot/actuador
        IR), pasa obligatoriamente por su verificación fail-closed —
        `ChainCommunicator`/MQTT solo se usa para el resto (cámaras y
        sensores ya operativos vía edge-gateway), nunca como atajo para
        equipo físico gobernado por el registro."""
        adapter = None
        if self.equipment and target_device_id:
            adapter = next((a for a in self.equipment.all() if a.equipment_id == target_device_id), None)
        if adapter is None:
            await self.chain.dispatch(action_id, action_type, target_device_id, zone, payload)
            return
        now = time.time()
        command = EquipmentCommand(
            command_id=action_id, nonce=uuid.uuid4().hex, equipment_type=adapter.equipment_type,
            equipment_id=target_device_id, action=payload.get("equipment_action", action_type.lower().replace("_", "-")),
            parameters=payload, issued_at=now, expires_at=now + 30,
            issued_by="agent-orchestrator", signature="",
        )
        # CORRECCIÓN: antes se usaba una firma estática del entorno que NUNCA coincidía con el HMAC del
        # comando canónico, así que todo comando real era rechazado. Se firma con la clave del equipo;
        # sin clave provisionada queda la firma legada (o vacía) y el registro rechaza fail-closed.
        command = dataclasses.replace(command, signature=sign_for_equipment(command) or os.getenv("EQUIPMENT_COMMAND_SIGNATURE", ""))
        try:
            outcome = await self.equipment.dispatch(command)
        except Exception as exc:  # noqa: BLE001
            log.exception("dispatch de equipo falló (%s)", target_device_id)
            async with self.pool.acquire() as c:
                await c.execute("UPDATE agent_actions SET status=$2 WHERE action_id=$1", action_id, "EQUIPMENT_ERROR")
            raise
        async with self.pool.acquire() as c:
            await c.execute(
                "UPDATE agent_actions SET status=$2 WHERE action_id=$1",
                action_id, f"EQUIPMENT_{outcome.status.upper()}" + (f":{outcome.reason}" if outcome.reason else ""),
            )

    async def handle_incident(self, incident: Incident):
        advisory = await self.neural.advise(incident)
        for agent in self.agents:
            if not agent.relevant(incident):
                continue
            try:
                proposal = agent.assess(incident)
            except Exception:  # noqa: BLE001 - un agente defectuoso no debe bloquear a los demás ni reencolar el incidente
                AGENT_ERRORS.labels(agent.name).inc()
                log.exception("agente %s falló evaluando incidente %s", agent.name, incident.incident_id)
                continue
            if proposal is None:
                continue
            PROPOSALS.labels(agent.name, proposal.action_type).inc()
            await self._record_and_act(incident, proposal, advisory)
        self.status["last_incident"] = {"incident_id": incident.incident_id, "kind": incident.kind, "at": time.time()}

    async def _record_and_act(self, incident: Incident, proposal: ActionProposal, advisory: dict | None = None):
        # Entrega at-least-once: si el mismo incidente se reentrega, no se duplica la propuesta (ni la acción física).
        async with self.pool.acquire() as c:
            already = await c.fetchval(
                "SELECT 1 FROM agent_actions WHERE incident_id=$1 AND agent_name=$2 AND action_type=$3 LIMIT 1",
                incident.incident_id, proposal.agent_name, proposal.action_type,
            )
        if already:
            DUPLICATE_PROPOSALS.inc()
            return
        async with self.pool.acquire() as c:
            row = await c.fetchrow(
                """INSERT INTO agent_actions(incident_id,agent_name,action_type,severity,target_device_id,zone,rationale,payload,status)
                   VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING action_id""",
                incident.incident_id, proposal.agent_name, proposal.action_type, proposal.severity,
                proposal.target_device_id, proposal.zone, proposal.rationale,
                json.dumps({**proposal.payload, "neural_advisory": advisory} if advisory else proposal.payload), "PENDING_APPROVAL" if proposal.requires_human_approval else "AUTO_APPROVED",
            )
        action_id = str(row["action_id"])
        if proposal.requires_human_approval:
            try:
                await self.gate.enqueue(action_id, proposal.severity)
            except Exception:
                # Sin fila de aprobación la acción quedaría PENDING_APPROVAL para siempre y sin fallback.
                async with self.pool.acquire() as c:
                    await c.execute("UPDATE agent_actions SET status='APPROVAL_ENQUEUE_FAILED',resolved_at=now() WHERE action_id=$1", action_id)
                raise
            return
        AUTO_EXECUTED.inc()
        await self._dispatch(action_id, proposal.action_type, proposal.target_device_id, proposal.zone, proposal.payload)

    async def apply_approved(self, approval_id: str, action_id: str, action_type: str, target_device_id: str | None, zone: str | None, payload: dict):
        await self._dispatch(action_id, action_type, target_device_id, zone, payload)

    async def run_forever(self):
        """Loop de fondo. Una excepción NO puede matar la tarea: antes, un fallo puntual de BD detenía
        para siempre el barrido de aprobaciones vencidas (y por tanto el fallback seguro)."""
        backoff = 1.0
        while True:
            await asyncio.sleep(self.tick_s)
            try:
                LOOP_ITER.inc()
                expired = await self.gate.sweep_expired()
                for e in expired:
                    FALLBACK.inc()
                    try:
                        # Reflect: la orden original no se ejecuta; se aplica el fallback seguro configurado.
                        await self._dispatch(str(e["action_id"]), e["fallback_action"], None, None, {"reason": "approval_timeout"})
                    except Exception:  # noqa: BLE001
                        LOOP_ERRORS.inc()
                        log.exception("fallback seguro falló para acción %s", e["action_id"])
                pending = await self.gate.pending()
                self.status["pending_approvals"] = len(pending)
                self.status["last_tick"] = time.time()
                PENDING_GAUGE.set(len(pending))
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                LOOP_ERRORS.inc()
                log.exception("error en el loop del orquestador; se reintenta en %.0fs", backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
