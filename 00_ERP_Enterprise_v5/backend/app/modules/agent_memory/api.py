from __future__ import annotations
import json
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session
from backend.app.modules.agent_memory.service import content_hash

router=APIRouter(prefix='/agent-memory', tags=['agent-memory'])
class MemoryWrite(BaseModel):
    agent: str=Field(min_length=1,max_length=64)
    scope: str=Field(default='tenant',pattern='^(tenant|property|asset|incident|workflow|agent)$')
    subject_key: str|None=Field(default=None,max_length=255)
    memory_type: str=Field(pattern='^(fact|observation|decision|outcome|preference|constraint)$')
    content: dict
    importance: int=Field(default=50,ge=0,le=100)
    embedding: list[float]|None=None
    source: str|None=Field(default=None,max_length=160)

@router.post('/memories',status_code=201)
async def write_memory(req:MemoryWrite,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    mid=uuid4(); h=content_hash(req.content)
    await session.execute(text('''INSERT INTO agent_memory_records(memory_id,tenant_id,agent,scope,subject_key,memory_type,content,content_hash,importance,embedding,source) VALUES(:id,:t,:a,:s,:k,:m,CAST(:c AS jsonb),:h,:i,:e,:src) ON CONFLICT(tenant_id,agent,content_hash) DO UPDATE SET updated_at=now(),importance=EXCLUDED.importance,content=EXCLUDED.content,embedding=EXCLUDED.embedding'''),{'id':mid,'t':UUID(auth.tenant_id),'a':req.agent,'s':req.scope,'k':req.subject_key,'m':req.memory_type,'c':json.dumps(req.content),'h':h,'i':req.importance,'e':req.embedding,'src':req.source})
    return {'memory_id':str(mid),'content_hash':h,'status':'persisted'}

@router.get('/memories')
async def list_memories(agent:str|None=None,subject_key:str|None=None,limit:int=50,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    limit=max(1,min(limit,200)); rows=(await session.execute(text('''SELECT memory_id,agent,scope,subject_key,memory_type,content,importance,source,expires_at,created_at,updated_at FROM agent_memory_records WHERE tenant_id=:t AND (CAST(:a AS text) IS NULL OR agent=:a) AND (CAST(:k AS text) IS NULL OR subject_key=:k) AND (expires_at IS NULL OR expires_at>now()) ORDER BY importance DESC,created_at DESC LIMIT :lim'''),{'t':UUID(auth.tenant_id),'a':agent,'k':subject_key,'lim':limit})).mappings().all()
    return [dict(r) for r in rows]
