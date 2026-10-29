from __future__ import annotations
import json
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session
from backend.app.modules.agent_execution.service import canonical_hash, decide, ToolPolicy

router = APIRouter(prefix="/agent-execution", tags=["agent-execution"])

class ExecuteRequest(BaseModel):
    request_id: UUID = Field(default_factory=uuid4)
    agent: str = Field(min_length=1, max_length=64)
    tool: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=160)
    payload: dict = Field(default_factory=dict)
    approval_id: UUID | None = None

class PolicyRequest(BaseModel):
    tool_name: str = Field(min_length=1, max_length=120)
    risk_level: str = Field(pattern="^(read|low|medium|high|critical)$")
    requires_human_approval: bool = True
    enabled: bool = True
    allowed_agents: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    max_payload_bytes: int = Field(default=65536, ge=1, le=1048576)

class ApprovalRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    reason: str = Field(min_length=1, max_length=1000)


@router.post("/policies", status_code=201)
async def create_policy(req: PolicyRequest, auth: AuthContext = Depends(get_auth_context), session=Depends(get_tenant_session)):
    if not ({"admin", "administrator", "security_admin"} & set(auth.roles)):
        raise HTTPException(403, {"code":"ADMIN_ROLE_REQUIRED"})
    policy_id=uuid4()
    await session.execute(text("""INSERT INTO agent_tool_policies(policy_id,tenant_id,tool_name,risk_level,requires_human_approval,enabled,allowed_agents,allowed_actions,max_payload_bytes) VALUES(:id,:t,:tool,:risk,:approval,:enabled,CAST(:agents AS jsonb),CAST(:actions AS jsonb),:max) ON CONFLICT(tenant_id,tool_name) DO UPDATE SET risk_level=EXCLUDED.risk_level,requires_human_approval=EXCLUDED.requires_human_approval,enabled=EXCLUDED.enabled,allowed_agents=EXCLUDED.allowed_agents,allowed_actions=EXCLUDED.allowed_actions,max_payload_bytes=EXCLUDED.max_payload_bytes,updated_at=now() RETURNING policy_id"""), {"id":policy_id,"t":UUID(auth.tenant_id),"tool":req.tool_name,"risk":req.risk_level,"approval":req.requires_human_approval,"enabled":req.enabled,"agents":json.dumps(req.allowed_agents),"actions":json.dumps(req.allowed_actions),"max":req.max_payload_bytes})
    return {"policy_id":str(policy_id),"tool_name":req.tool_name,"status":"configured"}

@router.get("/policies")
async def policies(auth: AuthContext = Depends(get_auth_context), session=Depends(get_tenant_session)):
    rows=(await session.execute(text("SELECT policy_id,tool_name,risk_level,requires_human_approval,enabled,allowed_agents,allowed_actions,max_payload_bytes,created_at,updated_at FROM agent_tool_policies WHERE tenant_id=:t ORDER BY tool_name"),{"t":UUID(auth.tenant_id)})).mappings().all()
    return [dict(r) for r in rows]

@router.post("/execute", status_code=202)
async def execute(req: ExecuteRequest, auth: AuthContext = Depends(get_auth_context), session=Depends(get_tenant_session)):
    policy_row = (await session.execute(text("""SELECT tool_name,risk_level,requires_human_approval,enabled,allowed_agents,allowed_actions,max_payload_bytes FROM agent_tool_policies WHERE tenant_id=:t AND tool_name=:tool"""), {"t": UUID(auth.tenant_id), "tool": req.tool})).mappings().first()
    if not policy_row:
        raise HTTPException(403, {"code": "TOOL_NOT_REGISTERED"})
    
    if policy_row["allowed_agents"] and req.agent not in policy_row["allowed_agents"]:
        raise HTTPException(403, {"code": "AGENT_NOT_ALLOWED_FOR_TOOL"})
    if policy_row["allowed_actions"] and req.action not in policy_row["allowed_actions"]:
        raise HTTPException(403, {"code": "ACTION_NOT_ALLOWED_FOR_TOOL"})
    if len(json.dumps(req.payload, ensure_ascii=False).encode()) > int(policy_row["max_payload_bytes"]):
        raise HTTPException(413, {"code": "TOOL_PAYLOAD_TOO_LARGE"})
    policy = ToolPolicy(policy_row["tool_name"], policy_row["risk_level"], policy_row["requires_human_approval"], policy_row["enabled"])
    approved = False
    if req.approval_id:
        approved = bool(await session.scalar(text("SELECT 1 FROM agent_workflow_approvals WHERE tenant_id=:t AND approval_id=:a AND decision='approved'"), {"t": UUID(auth.tenant_id), "a": req.approval_id}))
    decision = decide(policy=policy, requested_by=auth.user_id, approved=approved)
    digest = canonical_hash(req.payload)
    if not decision.allowed and decision.status == "rejected":
        raise HTTPException(403, {"code": decision.reason})
    existing = (await session.execute(text("SELECT execution_id,status FROM agent_tool_executions WHERE tenant_id=:t AND request_id=:r"), {"t": UUID(auth.tenant_id), "r": req.request_id})).mappings().first()
    if existing:
        return {"execution_id": str(existing["execution_id"]), "request_id": str(req.request_id), "status": existing["status"], "idempotent_replay": True}
    execution_id = uuid4()
    await session.execute(text("""INSERT INTO agent_tool_executions(execution_id,tenant_id,request_id,agent,tool_name,action,input_hash,status,requires_human_approval,approval_id,requested_by,payload) VALUES(:id,:t,:r,:agent,:tool,:action,:hash,:status,:req,:approval,:user,CAST(:payload AS jsonb))"""), {"id":execution_id,"t":UUID(auth.tenant_id),"r":req.request_id,"agent":req.agent,"tool":req.tool,"action":req.action,"hash":digest,"status":decision.status,"req":decision.requires_human_approval,"approval":req.approval_id,"user":auth.user_id,"payload":json.dumps(req.payload)})
    return {"execution_id": str(execution_id), "request_id": str(req.request_id), "status": decision.status, "reason": decision.reason, "input_hash": digest, "adapter_dispatch": False}

@router.post("/executions/{execution_id}/approval", status_code=200)
async def approve(execution_id: UUID, req: ApprovalRequest, auth: AuthContext = Depends(get_auth_context), session=Depends(get_tenant_session)):
    if not ({"operator", "admin", "administrator", "security_admin"} & set(auth.roles)):
        raise HTTPException(403, {"code":"APPROVAL_ROLE_REQUIRED"})
    row = (await session.execute(text("SELECT execution_id,agent,tool_name,action,input_hash,status FROM agent_tool_executions WHERE tenant_id=:t AND execution_id=:e"), {"t": UUID(auth.tenant_id), "e": execution_id})).mappings().first()
    if not row: raise HTTPException(404, "execution not found")
    if row["status"] != "awaiting_human": raise HTTPException(409, {"code":"EXECUTION_NOT_AWAITING_APPROVAL"})
    approval_id=uuid4()
    await session.execute(text("INSERT INTO agent_workflow_approvals(approval_id,tenant_id,execution_id,decision,reason,approved_by) VALUES(:id,:t,:e,:d,:r,:u)"), {"id":approval_id,"t":UUID(auth.tenant_id),"e":execution_id,"d":req.decision,"r":req.reason,"u":auth.user_id})
    new_status='approved' if req.decision=='approved' else 'rejected'
    await session.execute(text("UPDATE agent_tool_executions SET status=:s,approval_id=:a,updated_at=now() WHERE tenant_id=:t AND execution_id=:e"), {"s": 'accepted' if new_status=='approved' else 'rejected',"a":approval_id,"t":UUID(auth.tenant_id),"e":execution_id})
    return {"approval_id":str(approval_id),"execution_id":str(execution_id),"status":new_status}

@router.get("/executions")
async def executions(auth: AuthContext = Depends(get_auth_context), session=Depends(get_tenant_session)):
    rows=(await session.execute(text("SELECT execution_id,request_id,agent,tool_name,action,status,requires_human_approval,approval_id,requested_by,input_hash,created_at,updated_at,result,error_code FROM agent_tool_executions WHERE tenant_id=:t ORDER BY created_at DESC LIMIT 200"),{"t":UUID(auth.tenant_id)})).mappings().all()
    return [dict(r) for r in rows]


@router.post("/executions/{execution_id}/operations", status_code=201)
async def start_operation(execution_id: UUID, auth: AuthContext = Depends(get_auth_context), session=Depends(get_tenant_session)):
    """Puente agente -> mundo físico: una ejecución ACEPTADA abre una operación autónoma 'executing'.
    Sin esto, physical-edge no podía emitir ningún comando (nadie creaba autonomous_operations)."""
    if not ({"operator", "admin", "administrator", "security_admin"} & set(auth.roles)):
        raise HTTPException(403, {"code": "OPERATOR_ROLE_REQUIRED"})
    t = UUID(auth.tenant_id)
    row = (await session.execute(text("SELECT status FROM agent_tool_executions WHERE tenant_id=:t AND execution_id=:e FOR UPDATE"), {"t": t, "e": execution_id})).mappings().first()
    if not row: raise HTTPException(404, "execution not found")
    if row["status"] != "accepted": raise HTTPException(409, {"code": "EXECUTION_NOT_ACCEPTED"})
    existing = (await session.execute(text("SELECT operation_id FROM autonomous_operations WHERE tenant_id=:t AND execution_id=:e"), {"t": t, "e": execution_id})).scalar_one_or_none()
    if existing: return {"operation_id": str(existing), "state": "executing", "idempotent_replay": True}
    op = uuid4()
    await session.execute(text("INSERT INTO autonomous_operations(tenant_id,operation_id,state,execution_id) VALUES(:t,:o,'executing',:e)"), {"t": t, "o": op, "e": execution_id})
    from backend.app.platform.realtime.service import publish
    await publish(session, tenant_id=t, topic="agent.operation.started", payload={"operation_id": str(op), "execution_id": str(execution_id)}, correlation_id=str(op))
    return {"operation_id": str(op), "state": "executing"}
