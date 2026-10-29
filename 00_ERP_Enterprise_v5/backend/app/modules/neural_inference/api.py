from __future__ import annotations
import json
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import text
from backend.app.api.deps import AuthContext,get_auth_context,get_tenant_session
from backend.app.modules.neural_inference.service import canonical_hash
router=APIRouter(prefix='/neural',tags=['neural'])
class ModelRegistration(BaseModel):
    name:str=Field(min_length=1,max_length=120); version:str=Field(min_length=1,max_length=64)
    framework:str=Field(min_length=1,max_length=32); format:str=Field(pattern='^(onnx|json_weights)$')
    artifact_uri:str=Field(min_length=1,max_length=1000); sha256:str=Field(pattern='^[0-9a-fA-F]{64}$')
    input_schema:dict; output_schema:dict; approved_for_inference:bool=False
class InferenceAudit(BaseModel):
    model_id:UUID; request_id:UUID=Field(default_factory=uuid4); agent:str|None=None; subject_key:str|None=None
    input:dict; output:dict|None=None; status:str=Field(pattern='^(completed|rejected|failed|unavailable)$')
    confidence:float|None=Field(default=None,ge=0,le=1); error_code:str|None=None; latency_ms:int|None=Field(default=None,ge=0)
@router.post('/models',status_code=201)
async def register_model(req:ModelRegistration,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    if not ({'admin','administrator','security_admin'} & set(auth.roles)): raise HTTPException(403,'ADMIN_ROLE_REQUIRED')
    mid=uuid4(); await session.execute(text('''INSERT INTO neural_model_registry(model_id,tenant_id,name,version,framework,format,artifact_uri,sha256,input_schema,output_schema,approved_for_inference,status) VALUES(:id,:t,:n,:v,:f,:fmt,:u,:h,CAST(:i AS jsonb),CAST(:o AS jsonb),:a,'validated') ON CONFLICT(tenant_id,name,version) DO UPDATE SET artifact_uri=EXCLUDED.artifact_uri,sha256=EXCLUDED.sha256,input_schema=EXCLUDED.input_schema,output_schema=EXCLUDED.output_schema,approved_for_inference=EXCLUDED.approved_for_inference,updated_at=now()'''),{'id':mid,'t':UUID(auth.tenant_id),'n':req.name,'v':req.version,'f':req.framework,'fmt':req.format,'u':req.artifact_uri,'h':req.sha256.lower(),'i':json.dumps(req.input_schema),'o':json.dumps(req.output_schema),'a':req.approved_for_inference})
    return {'model_id':str(mid),'status':'validated' if req.approved_for_inference else 'registered','inference_enabled':req.approved_for_inference}
@router.get('/models')
async def models(auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    rows=(await session.execute(text('SELECT model_id,name,version,framework,format,artifact_uri,sha256,status,approved_for_inference,created_at,updated_at FROM neural_model_registry WHERE tenant_id=:t OR tenant_id IS NULL ORDER BY name,version'),{'t':UUID(auth.tenant_id)})).mappings().all(); return [dict(r) for r in rows]
@router.post('/inference-audit',status_code=201)
async def audit_inference(req:InferenceAudit,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    row=(await session.execute(text('SELECT model_id,approved_for_inference FROM neural_model_registry WHERE model_id=:m AND (tenant_id=:t OR tenant_id IS NULL)'),{'m':req.model_id,'t':UUID(auth.tenant_id)})).mappings().first()
    if not row: raise HTTPException(404,'MODEL_NOT_FOUND')
    if req.status=='completed' and not row['approved_for_inference']: raise HTTPException(409,'MODEL_NOT_APPROVED')
    iid=uuid4(); await session.execute(text('''INSERT INTO neural_inference_audit(inference_id,tenant_id,model_id,request_id,agent,subject_key,input_hash,output_hash,status,confidence,output,error_code,latency_ms) VALUES(:id,:t,:m,:r,:a,:s,:ih,:oh,:st,:c,CAST(:o AS jsonb),:e,:l) ON CONFLICT(tenant_id,request_id) DO NOTHING'''),{'id':iid,'t':UUID(auth.tenant_id),'m':req.model_id,'r':req.request_id,'a':req.agent,'s':req.subject_key,'ih':canonical_hash(req.input),'oh':canonical_hash(req.output) if req.output is not None else None,'st':req.status,'c':req.confidence,'o':json.dumps(req.output) if req.output is not None else None,'e':req.error_code,'l':req.latency_ms})
    return {'inference_id':str(iid),'input_hash':canonical_hash(req.input),'status':req.status}
