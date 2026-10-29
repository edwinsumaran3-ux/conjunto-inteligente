from __future__ import annotations
import json,os
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import text
from backend.app.api.deps import AuthContext,get_auth_context,get_tenant_session
from .service import attest_payload,sign_attestation,verify_attestation,reconcile,rollout_allowed,select_rollout_batch,evaluate_chaos
router=APIRouter(prefix='/edge-trust',tags=['edge-trust'])
def key():
    k=os.getenv('EDGE_FLEET_SIGNING_KEY','')
    if len(k)<32: raise HTTPException(503,'EDGE_FLEET_SIGNING_KEY_NOT_CONFIGURED')
    return k.encode()
def op_role(a):
    if not ({'operator','admin','administrator','security_admin'}&set(a.roles)): raise HTTPException(403,'OPERATOR_ROLE_REQUIRED')
class Attestation(BaseModel):
    device_id:UUID; nonce:str=Field(min_length=8,max_length=160); boot_id:str; firmware_hash:str=Field(min_length=64,max_length=64); measurement_hash:str=Field(min_length=64,max_length=64); signature:str
class Recon(BaseModel): device_id:UUID; device_sequence:int=Field(ge=0); server_sequence:int=Field(ge=0); seen_sequences:list[int]=[]
class Rollout(BaseModel): platform:str; ring:str; healthy_percent:float=Field(ge=0,le=100); failure_percent:float=Field(ge=0,le=100)
class Chaos(BaseModel): scenario:str; target_device_id:UUID|None=None; observed_state:str=Field(pattern='^(armed|safe|kill_switch|quarantined)$')
@router.post('/attest',status_code=201)
async def attest(r:Attestation,a:AuthContext=Depends(get_auth_context),s=Depends(get_tenant_session)):
    t=UUID(a.tenant_id); payload=attest_payload(r.device_id,r.nonce,r.boot_id,r.firmware_hash,r.measurement_hash); valid=verify_attestation(payload,r.signature,key())
    reason=None if valid else 'SIGNATURE_INVALID'
    aid=uuid4(); await s.execute(text("INSERT INTO edge_attestations(attestation_id,tenant_id,device_id,nonce,boot_id,firmware_hash,measurement_hash,signature,verified,failure_reason) VALUES(:i,:t,:d,:n,:b,:f,:m,:s,:v,:r)"),{'i':aid,'t':t,'d':r.device_id,'n':r.nonce,'b':r.boot_id,'f':r.firmware_hash,'m':r.measurement_hash,'s':r.signature,'v':valid,'r':reason})
    if valid: await s.execute(text("UPDATE edge_devices SET status='online',updated_at=now() WHERE tenant_id=:t AND device_id=:d"),{'t':t,'d':r.device_id})
    await s.commit()
    if not valid: raise HTTPException(401,reason)
    return {'attestation_id':str(aid),'verified':True}
@router.post('/reconcile')
async def recon(r:Recon,a:AuthContext=Depends(get_auth_context),s=Depends(get_tenant_session)):
    op_role(a); t=UUID(a.tenant_id); result=reconcile(r.device_sequence,r.server_sequence,r.seen_sequences); rid=uuid4(); await s.execute(text("INSERT INTO edge_reconciliation_runs(reconciliation_id,tenant_id,device_id,last_device_sequence,last_server_sequence,missing_count,duplicate_count,conflict_count,status,completed_at,evidence) VALUES(:i,:t,:d,:ds,:ss,:m,:du,:c,:st,now(),CAST(:e AS jsonb))"),{'i':rid,'t':t,'d':r.device_id,'ds':r.device_sequence,'ss':r.server_sequence,'m':result['missing'],'du':result['duplicates'],'c':result['conflicts'],'st':result['status'],'e':json.dumps(result)}); await s.commit(); return {'reconciliation_id':str(rid),**result}
@router.post('/rollout/check')
async def rollout(r:Rollout,a:AuthContext=Depends(get_auth_context),s=Depends(get_tenant_session)):
    op_role(a); t=UUID(a.tenant_id); p=(await s.execute(text("SELECT enabled,min_healthy_percent,max_failure_percent,max_concurrent,require_attestation,require_rollback_artifact FROM edge_rollout_policies WHERE tenant_id=:t AND platform=:p AND ring=:r"),{'t':t,'p':r.platform,'r':r.ring})).mappings().first()
    if not p: raise HTTPException(404,'ROLLOUT_POLICY_NOT_FOUND')
    allowed=rollout_allowed(r.healthy_percent,r.failure_percent,p); return {'allowed':allowed,'max_concurrent':p['max_concurrent'],'requires_attestation':p['require_attestation'],'requires_rollback_artifact':p['require_rollback_artifact']}
@router.post('/chaos',status_code=201)
async def chaos(r:Chaos,a:AuthContext=Depends(get_auth_context),s=Depends(get_tenant_session)):
    op_role(a); t=UUID(a.tenant_id); result=evaluate_chaos(r.scenario,r.observed_state); cid=uuid4(); await s.execute(text("INSERT INTO edge_chaos_runs(chaos_run_id,tenant_id,scenario,target_device_id,seed,status,observed_safe_state,evidence,started_at,completed_at) VALUES(:i,:t,:s,:d,0,:st,:safe,CAST(:e AS jsonb),now(),now())"),{'i':cid,'t':t,'s':r.scenario,'d':r.target_device_id,'st':'passed' if result.passed else 'failed','safe':result.observed_safe,'e':json.dumps({'expected_safe':result.expected_safe})}); await s.commit(); return {'chaos_run_id':str(cid),'passed':result.passed}
