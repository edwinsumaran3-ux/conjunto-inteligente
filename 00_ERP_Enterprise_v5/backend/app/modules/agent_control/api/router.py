import hashlib, json
from datetime import datetime, timezone
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session

router=APIRouter(prefix='/agent-control',tags=['agent-control'])
class ExecutionIn(BaseModel):
    request_id: UUID=Field(default_factory=uuid4); trace_id: UUID|None=None; agent: str=Field(min_length=1,max_length=64)
    action: str=Field(min_length=1,max_length=200); payload: dict=Field(default_factory=dict); status: str=Field(default='accepted',pattern='^(accepted|completed|rejected|failed|awaiting_human)$')
    requires_human_review: bool=True; policy_reason: str=Field(min_length=1,max_length=1000); tool_calls: list[str]=Field(default_factory=list); warnings:list[str]=Field(default_factory=list); result:dict|None=None; error_code:str|None=None
class MemoryIn(BaseModel):
    memory_id: UUID=Field(default_factory=uuid4); agent:str=Field(min_length=1,max_length=64); source:str=Field(min_length=1,max_length=500)
    content:dict; confidence:float=Field(ge=0,le=1); version:int=Field(ge=1); expires_at:datetime|None=None

@router.post('/executions',status_code=201)
async def record_execution(body:ExecutionIn,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    raw=json.dumps(body.payload,sort_keys=True,separators=(',',':'),default=str).encode(); digest=hashlib.sha256(raw).hexdigest()
    try:
        await session.execute(text("""INSERT INTO agent_executions(execution_id,request_id,trace_id,tenant_id,agent,action,input_hash,status,requires_human_review,policy_reason,tool_calls,warnings,result,error_code,completed_at) VALUES(:id,:r,:tr,:t,:a,:ac,:h,:s,:hr,:pr,CAST(:tc AS jsonb),CAST(:w AS jsonb),CAST(:res AS jsonb),:err,CASE WHEN :s IN ('completed','rejected','failed') THEN now() ELSE NULL END)"""),{'id':uuid4(),'r':body.request_id,'tr':body.trace_id,'t':UUID(auth.tenant_id),'a':body.agent,'ac':body.action,'h':digest,'s':body.status,'hr':body.requires_human_review,'pr':body.policy_reason,'tc':json.dumps(body.tool_calls),'w':json.dumps(body.warnings),'res':json.dumps(body.result) if body.result is not None else None,'err':body.error_code})
    except Exception as exc: raise HTTPException(409,'request_id already exists for this tenant or violates a constraint') from exc
    return {'request_id':str(body.request_id),'input_hash':digest,'status':body.status}

@router.post('/memories',status_code=201)
async def write_memory(body:MemoryIn,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    await session.execute(text("""INSERT INTO agent_memories(memory_id,tenant_id,agent,source,content,confidence,version,expires_at) VALUES(:id,:t,:a,:s,CAST(:c AS jsonb),:cf,:v,:e)"""),{'id':body.memory_id,'t':UUID(auth.tenant_id),'a':body.agent,'s':body.source,'c':json.dumps(body.content),'cf':body.confidence,'v':body.version,'e':body.expires_at})
    return {'memory_id':str(body.memory_id),'status':'stored'}

@router.get('/executions')
async def list_executions(limit:int=Query(100,ge=1,le=500),agent:str|None=None,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    q="SELECT execution_id,request_id,trace_id,agent,action,status,requires_human_review,policy_reason,tool_calls,warnings,started_at,completed_at,result,error_code FROM agent_executions WHERE tenant_id=:t"
    params={'t':UUID(auth.tenant_id),'limit':limit}
    if agent: q+=' AND agent=:a'; params['a']=agent
    q+=' ORDER BY started_at DESC LIMIT :limit'
    return [dict(x) for x in (await session.execute(text(q),params)).mappings().all()]

@router.get('/memories')
async def list_memories(agent:str,limit:int=Query(100,ge=1,le=500),auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    rows=(await session.execute(text("SELECT memory_id,agent,source,content,confidence,version,created_at,expires_at FROM agent_memories WHERE tenant_id=:t AND agent=:a AND (expires_at IS NULL OR expires_at>now()) ORDER BY created_at DESC LIMIT :limit"),{'t':UUID(auth.tenant_id),'a':agent,'limit':limit})).mappings().all()
    return [dict(x) for x in rows]
