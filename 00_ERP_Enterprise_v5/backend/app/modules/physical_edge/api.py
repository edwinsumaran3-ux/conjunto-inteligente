from __future__ import annotations
import json, os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy import text
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session
from .service import canonical_json, sha256_json, sign_envelope, verify_signature, key_fingerprint, command_allowed, safety_allows

router=APIRouter(prefix='/physical-edge',tags=['physical-edge'])

def _secret()->bytes:
    raw=os.getenv('EDGE_COMMAND_HMAC_KEY','')
    if len(raw)<32: raise HTTPException(503,'EDGE_SIGNING_KEY_NOT_CONFIGURED')
    return raw.encode()

def _operator(auth:AuthContext):
    if not ({'operator','admin','administrator','security_admin'} & set(auth.roles)): raise HTTPException(403,'OPERATOR_ROLE_REQUIRED')

class DeviceRegister(BaseModel):
    name:str=Field(min_length=1,max_length=160); device_type:str=Field(min_length=1,max_length=40)
    node_id:UUID|None=None; capabilities:list[str]=Field(default_factory=list,max_length=100); key_ref:str=Field(min_length=1,max_length=200)

class CommandRequest(BaseModel):
    device_id:UUID; operation_id:UUID; command_type:str=Field(min_length=1,max_length=80); payload:dict={}; ttl_seconds:int=Field(default=30,ge=1,le=300)

class AckRequest(BaseModel):
    command_id:UUID; sequence:int=Field(ge=0); status:str=Field(pattern='^(acknowledged|completed|failed|rejected)$'); result:dict={}; signature:str=Field(min_length=64,max_length=128)

class HeartbeatRequest(BaseModel):
    sequence:int=Field(ge=0); firmware_version:str=Field(default='',max_length=120); connectivity:dict={}; health:dict={}; safety_state:str=Field(pattern='^(armed|safe|kill_switch|quarantined)$'); signature:str|None=None

@router.post('/devices',status_code=201)
async def register(req:DeviceRegister,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    _operator(auth); secret=_secret(); tenant=UUID(auth.tenant_id); fp=key_fingerprint(secret); did=uuid4()
    await session.execute(text("""INSERT INTO edge_devices(device_id,tenant_id,node_id,device_type,name,key_ref,key_fingerprint,capabilities) VALUES(:d,:t,:n,:ty,:name,:kr,:fp,CAST(:cap AS jsonb))"""),{'d':did,'t':tenant,'n':req.node_id,'ty':req.device_type,'name':req.name,'kr':req.key_ref,'fp':fp,'cap':json.dumps(req.capabilities)})
    await session.commit(); return {'device_id':str(did),'key_fingerprint':fp,'safety_state':'armed'}

@router.post('/commands',status_code=201)
async def issue(req:CommandRequest,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    _operator(auth); secret=_secret(); tenant=UUID(auth.tenant_id)
    dev=(await session.execute(text('SELECT capabilities,safety_state,status,last_sequence FROM edge_devices WHERE tenant_id=:t AND device_id=:d FOR UPDATE'),{'t':tenant,'d':req.device_id})).mappings().first()
    if not dev: raise HTTPException(404,'EDGE_DEVICE_NOT_FOUND')
    if dev['status'] in ('quarantined','retired') or not safety_allows(dev['safety_state'],req.command_type): raise HTTPException(409,'EDGE_SAFETY_STATE_BLOCKS_COMMAND')
    caps=dev['capabilities'] or []
    if not command_allowed(req.command_type,caps): raise HTTPException(403,'EDGE_COMMAND_NOT_CAPABILITY_ALLOWED')
    op=(await session.execute(text('SELECT state,execution_id FROM autonomous_operations WHERE tenant_id=:t AND operation_id=:o'),{'t':tenant,'o':req.operation_id})).mappings().first()
    if not op or op['state']!='executing': raise HTTPException(409,'OPERATION_NOT_EXECUTING')
    ex=(await session.execute(text('SELECT status FROM agent_tool_executions WHERE tenant_id=:t AND execution_id=:e'),{'t':tenant,'e':op['execution_id']})).mappings().first()
    if not ex or ex['status']!='accepted': raise HTTPException(409,'EXECUTION_NOT_ACCEPTED')
    seq=int(dev['last_sequence'])+1; cid=uuid4(); nonce=uuid4().hex; now=datetime.now(timezone.utc); expires=now+timedelta(seconds=req.ttl_seconds)
    envelope={'command_id':str(cid),'tenant_id':str(tenant),'device_id':str(req.device_id),'operation_id':str(req.operation_id),'command_type':req.command_type,'sequence':seq,'nonce':nonce,'issued_at':now.isoformat(),'expires_at':expires.isoformat(),'payload_hash':sha256_json(req.payload)}
    sig=sign_envelope(envelope,secret)
    await session.execute(text("""INSERT INTO edge_commands(command_id,tenant_id,device_id,operation_id,command_type,sequence,nonce,expires_at,payload,payload_hash,envelope,signature) VALUES(:c,:t,:d,:o,:ct,:s,:n,:x,CAST(:p AS jsonb),:ph,CAST(:e AS jsonb),:sig)"""),{'c':cid,'t':tenant,'d':req.device_id,'o':req.operation_id,'ct':req.command_type,'s':seq,'n':nonce,'x':expires,'p':json.dumps(req.payload),'ph':envelope['payload_hash'],'e':json.dumps(envelope),'sig':sig})
    from backend.app.platform.realtime.service import publish
    await publish(session,tenant_id=tenant,topic='edge.command.issued',payload={'command_id':str(cid),'device_id':str(req.device_id),'command_type':req.command_type,'sequence':seq},correlation_id=str(cid))
    await session.execute(text('UPDATE edge_devices SET last_sequence=:s,updated_at=now() WHERE tenant_id=:t AND device_id=:d'),{'s':seq,'t':tenant,'d':req.device_id}); await session.commit()
    return {'command_id':str(cid),'sequence':seq,'envelope':envelope,'signature':sig,'dispatch':'edge_pull_or_gateway'}

@router.get('/devices/{device_id}/commands')
async def pull(device_id:UUID,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    tenant=UUID(auth.tenant_id)
    rows=(await session.execute(text("SELECT command_id,envelope,payload,signature,sequence,expires_at,status FROM edge_commands WHERE tenant_id=:t AND device_id=:d AND status='issued' AND expires_at>now() ORDER BY sequence LIMIT 20"),{'t':tenant,'d':device_id})).mappings().all()
    return {'commands':[dict(r) for r in rows]}

@router.post('/ack')
async def ack(req:AckRequest,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    tenant=UUID(auth.tenant_id); secret=_secret()
    row=(await session.execute(text('SELECT device_id,envelope,status FROM edge_commands WHERE tenant_id=:t AND command_id=:c FOR UPDATE'),{'t':tenant,'c':req.command_id})).mappings().first()
    if not row: raise HTTPException(404,'COMMAND_NOT_FOUND')
    if row['status'] in ('completed','failed','rejected','cancelled'): raise HTTPException(409,'COMMAND_TERMINAL')
    env=row['envelope']; ack_env={'command_id':str(req.command_id),'device_id':str(row['device_id']),'sequence':req.sequence,'status':req.status,'result_hash':sha256_json(req.result)}
    if not verify_signature(ack_env,req.signature,secret): raise HTTPException(401,'INVALID_EDGE_SIGNATURE')
    if int(env['sequence'])!=req.sequence: raise HTTPException(409,'SEQUENCE_MISMATCH')
    await session.execute(text('UPDATE edge_commands SET status=:s,acknowledged_at=CASE WHEN :s=\'acknowledged\' THEN now() ELSE acknowledged_at END,completed_at=CASE WHEN :s IN (\'completed\',\'failed\',\'rejected\') THEN now() ELSE completed_at END,result=CAST(:r AS jsonb) WHERE tenant_id=:t AND command_id=:c'),{'s':req.status,'r':json.dumps(req.result),'t':tenant,'c':req.command_id})
    await session.commit(); return {'command_id':str(req.command_id),'status':req.status}

@router.post('/heartbeat')
async def heartbeat(device_id:UUID,req:HeartbeatRequest,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    tenant=UUID(auth.tenant_id); row=(await session.execute(text('SELECT safety_state FROM edge_devices WHERE tenant_id=:t AND device_id=:d'),{'t':tenant,'d':device_id})).mappings().first()
    if not row: raise HTTPException(404,'EDGE_DEVICE_NOT_FOUND')
    if req.signature:
        secret=_secret(); env={'device_id':str(device_id),'sequence':req.sequence,'firmware_version':req.firmware_version,'safety_state':req.safety_state,'connectivity_hash':sha256_json(req.connectivity),'health_hash':sha256_json(req.health)}
        if not verify_signature(env,req.signature,secret): raise HTTPException(401,'INVALID_EDGE_SIGNATURE')
    await session.execute(text("INSERT INTO edge_heartbeats(tenant_id,device_id,sequence,firmware_version,connectivity,health,safety_state,signature) VALUES(:t,:d,:s,:f,CAST(:c AS jsonb),CAST(:h AS jsonb),:ss,:sig) ON CONFLICT(tenant_id,device_id,sequence) DO NOTHING"),{'t':tenant,'d':device_id,'s':req.sequence,'f':req.firmware_version,'c':json.dumps(req.connectivity),'h':json.dumps(req.health),'ss':req.safety_state,'sig':req.signature})
    await session.execute(text("UPDATE edge_devices SET status='online',last_heartbeat_at=now(),safety_state=:ss,updated_at=now() WHERE tenant_id=:t AND device_id=:d"),{'ss':req.safety_state,'t':tenant,'d':device_id}); await session.commit(); return {'device_id':str(device_id),'accepted':True}

@router.post('/devices/{device_id}/safety')
async def safety(device_id:UUID,state:str,reason:str=Header(default='operator_request',alias='X-Safety-Reason'),auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    _operator(auth)
    if state not in {'armed','safe','kill_switch','quarantined'}: raise HTTPException(400,'INVALID_SAFETY_STATE')
    tenant=UUID(auth.tenant_id); row=(await session.execute(text('SELECT safety_state FROM edge_devices WHERE tenant_id=:t AND device_id=:d FOR UPDATE'),{'t':tenant,'d':device_id})).mappings().first()
    if not row: raise HTTPException(404,'EDGE_DEVICE_NOT_FOUND')
    await session.execute(text('UPDATE edge_devices SET safety_state=:s,status=CASE WHEN :s=\'quarantined\' THEN \'quarantined\' ELSE status END,updated_at=now() WHERE tenant_id=:t AND device_id=:d'),{'s':state,'t':tenant,'d':device_id})
    await session.execute(text('INSERT INTO edge_safety_events(tenant_id,device_id,actor,action,reason,previous_state,new_state) VALUES(:t,:d,:a,\'state_change\',:r,:p,:n)'),{'t':tenant,'d':device_id,'a':auth.user_id,'r':reason,'p':row['safety_state'],'n':state}); await session.commit()
    return {'device_id':str(device_id),'previous_state':row['safety_state'],'new_state':state}
