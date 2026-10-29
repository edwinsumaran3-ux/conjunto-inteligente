from __future__ import annotations
import json,os
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import text
from backend.app.api.deps import AuthContext,get_auth_context,get_tenant_session
from .service import sha256,sign_manifest,verify_manifest,ota_allowed,watchdog_state
router=APIRouter(prefix='/edge-fleet',tags=['edge-fleet'])
def key():
    k=os.getenv('EDGE_FLEET_SIGNING_KEY','');
    if len(k)<32: raise HTTPException(503,'EDGE_FLEET_SIGNING_KEY_NOT_CONFIGURED')
    return k.encode()
def op_role(a):
    if not ({'operator','admin','administrator','security_admin'}&set(a.roles)): raise HTTPException(403,'OPERATOR_ROLE_REQUIRED')
class Credential(BaseModel): device_id:UUID; algorithm:str=Field(pattern='^(ed25519|ecdsa|rsa)$'); public_key:str; fingerprint:str
class Firmware(BaseModel): version:str; platform:str; artifact_uri:str; sha256:str=Field(min_length=64,max_length=64); manifest:dict={}
class OTA(BaseModel): device_id:UUID; artifact_id:UUID; target_version:str; ring:str=Field(default='canary'); current_version:str=''
class Link(BaseModel): parent_device_id:UUID; child_device_id:UUID; priority:int=Field(default=100,ge=0,le=10000); latency_ms:float|None=None; packet_loss:float|None=None
class Spool(BaseModel): device_id:UUID; sequence:int=Field(ge=0); event_key:str; event_type:str; payload:dict={}
@router.post('/credentials',status_code=201)
async def credential(r:Credential,a:AuthContext=Depends(get_auth_context),s=Depends(get_tenant_session)):
    op_role(a); t=UUID(a.tenant_id); await s.execute(text("INSERT INTO edge_device_credentials(tenant_id,device_id,algorithm,public_key,fingerprint) VALUES(:t,:d,:a,:p,:f)"),{'t':t,'d':r.device_id,'a':r.algorithm,'p':r.public_key,'f':r.fingerprint}); await s.commit(); return {'fingerprint':r.fingerprint,'status':'active'}
@router.post('/firmware',status_code=201)
async def firmware(r:Firmware,a:AuthContext=Depends(get_auth_context),s=Depends(get_tenant_session)):
    op_role(a); t=UUID(a.tenant_id); manifest={**r.manifest,'version':r.version,'platform':r.platform,'sha256':r.sha256,'artifact_uri':r.artifact_uri}; sig=sign_manifest(manifest,key()); aid=uuid4(); await s.execute(text("INSERT INTO edge_firmware_artifacts(artifact_id,tenant_id,version,platform,artifact_uri,sha256,manifest,signature) VALUES(:i,:t,:v,:p,:u,:h,CAST(:m AS jsonb),:s)"),{'i':aid,'t':t,'v':r.version,'p':r.platform,'u':r.artifact_uri,'h':r.sha256,'m':json.dumps(manifest),'s':sig}); await s.commit(); return {'artifact_id':str(aid),'signature':sig,'manifest_hash':sha256(manifest)}
@router.post('/ota',status_code=201)
async def ota(r:OTA,a:AuthContext=Depends(get_auth_context),s=Depends(get_tenant_session)):
    op_role(a); t=UUID(a.tenant_id); art=(await s.execute(text('SELECT version,manifest,signature FROM edge_firmware_artifacts WHERE tenant_id=:t AND artifact_id=:i AND status=\'published\''),{'t':t,'i':r.artifact_id})).mappings().first()
    if not art or not verify_manifest(art['manifest'],art['signature'],key()): raise HTTPException(409,'FIRMWARE_MANIFEST_INVALID')
    if not ota_allowed(r.current_version,r.target_version,r.ring): raise HTTPException(409,'OTA_POLICY_BLOCKED')
    did=uuid4(); mh=sha256(art['manifest']); await s.execute(text("INSERT INTO edge_ota_deployments(deployment_id,tenant_id,artifact_id,device_id,ring,target_version,manifest_hash) VALUES(:i,:t,:a,:d,:r,:v,:h)"),{'i':did,'t':t,'a':r.artifact_id,'d':r.device_id,'r':r.ring,'v':r.target_version,'h':mh}); await s.commit(); return {'deployment_id':str(did),'status':'planned','manifest_hash':mh}
@router.post('/mesh',status_code=201)
async def mesh(r:Link,a:AuthContext=Depends(get_auth_context),s=Depends(get_tenant_session)):
    op_role(a); t=UUID(a.tenant_id); await s.execute(text("INSERT INTO edge_mesh_links(tenant_id,parent_device_id,child_device_id,priority,latency_ms,packet_loss,last_seen_at) VALUES(:t,:p,:c,:r,:l,:q,now()) ON CONFLICT(tenant_id,parent_device_id,child_device_id) DO UPDATE SET priority=excluded.priority,latency_ms=excluded.latency_ms,packet_loss=excluded.packet_loss,status='healthy',last_seen_at=now()"),{'t':t,'p':r.parent_device_id,'c':r.child_device_id,'r':r.priority,'l':r.latency_ms,'q':r.packet_loss}); await s.commit(); return {'status':'healthy'}
@router.post('/spool',status_code=201)
async def spool(r:Spool,a:AuthContext=Depends(get_auth_context),s=Depends(get_tenant_session)):
    t=UUID(a.tenant_id); h=sha256(r.payload); await s.execute(text("INSERT INTO edge_event_spool(tenant_id,device_id,event_key,sequence,event_type,payload,payload_hash) VALUES(:t,:d,:k,:q,:e,CAST(:p AS jsonb),:h) ON CONFLICT(tenant_id,device_id,sequence) DO NOTHING"),{'t':t,'d':r.device_id,'k':r.event_key,'q':r.sequence,'e':r.event_type,'p':json.dumps(r.payload),'h':h}); await s.commit(); return {'accepted':True,'payload_hash':h}
@router.post('/watchdog/{device_id}')
async def watchdog(device_id:UUID,timeout_seconds:int=60,a:AuthContext=Depends(get_auth_context),s=Depends(get_tenant_session)):
    op_role(a); t=UUID(a.tenant_id); row=(await s.execute(text('SELECT safety_state,last_heartbeat_at FROM edge_devices WHERE tenant_id=:t AND device_id=:d FOR UPDATE'),{'t':t,'d':device_id})).mappings().first()
    if not row: raise HTTPException(404,'EDGE_DEVICE_NOT_FOUND')
    new=watchdog_state(row['last_heartbeat_at'],timeout_seconds); old=row['safety_state']
    if new=='safe' and old=='armed': await s.execute(text("UPDATE edge_devices SET safety_state='safe',status='degraded',updated_at=now() WHERE tenant_id=:t AND device_id=:d"),{'t':t,'d':device_id})
    await s.execute(text("INSERT INTO edge_watchdog_events(tenant_id,device_id,last_heartbeat_at,timeout_seconds,action,previous_state,new_state,reason) VALUES(:t,:d,:h,:x,'safe_state_on_timeout',:o,:n,:r)"),{'t':t,'d':device_id,'h':row['last_heartbeat_at'],'x':timeout_seconds,'o':old,'n':new,'r':'heartbeat_timeout' if new=='safe' else 'heartbeat_healthy'}); await s.commit(); return {'device_id':str(device_id),'previous_state':old,'new_state':new}
