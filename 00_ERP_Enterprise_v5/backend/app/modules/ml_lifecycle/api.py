from __future__ import annotations
import json
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session
from .service import evaluation_gate, drift_action, deployment_allowed

router = APIRouter(prefix="/ml", tags=["ml-lifecycle"])

class FeatureRequest(BaseModel):
    name: str = Field(min_length=1,max_length=160); version: str = Field(min_length=1,max_length=32)
    source: str = Field(min_length=1,max_length=255); data_type: str = Field(min_length=1,max_length=32)
    definition: dict; status: str = Field(default="active", pattern="^(draft|active|retired)$")
class DatasetRequest(BaseModel):
    name: str = Field(min_length=1,max_length=160); version: str = Field(min_length=1,max_length=64)
    source_query_hash: str = Field(pattern="^[0-9a-fA-F]{64}$"); feature_ids: list[UUID]
    row_count: int = Field(ge=0); schema_hash: str = Field(pattern="^[0-9a-fA-F]{64}$")
    content_hash: str = Field(pattern="^[0-9a-fA-F]{64}$"); split: dict
class TrainingRequest(BaseModel):
    dataset_id: UUID; model_name: str = Field(min_length=1,max_length=120); candidate_version: str = Field(min_length=1,max_length=64)
    framework: str = Field(min_length=1,max_length=32); algorithm: str = Field(min_length=1,max_length=120); hyperparameters: dict = {}
class EvaluationRequest(BaseModel):
    training_id: UUID; model_id: UUID|None = None; gate: str = Field(min_length=1,max_length=80)
    primary_score: float = Field(ge=0,le=1); false_positive_rate: float = Field(ge=0,le=1)
    min_score: float = Field(default=.80,ge=0,le=1); max_false_positive_rate: float = Field(default=.10,ge=0,le=1)
    evaluator: str = Field(min_length=1,max_length=160)
class DriftRequest(BaseModel):
    model_id: UUID; feature_name: str = Field(min_length=1,max_length=160); metric: str = Field(min_length=1,max_length=64)
    value: float = Field(ge=0); threshold: float = Field(gt=0); window_start: str; window_end: str
class PromotionRequest(BaseModel):
    model_id: UUID; environment: str = Field(min_length=1,max_length=32); evaluation_passed: bool; artifact_verified: bool
    reason: str|None = Field(default=None,max_length=255)

@router.post("/features",status_code=201)
async def create_feature(req:FeatureRequest, auth:AuthContext=Depends(get_auth_context), session=Depends(get_tenant_session)):
    fid=uuid4(); await session.execute(text("""INSERT INTO ml_feature_definitions(feature_id,tenant_id,name,version,source,data_type,definition,status) VALUES(:id,:t,:n,:v,:s,:d,CAST(:def AS jsonb),:st) ON CONFLICT(tenant_id,name,version) DO UPDATE SET source=EXCLUDED.source,data_type=EXCLUDED.data_type,definition=EXCLUDED.definition,status=EXCLUDED.status,updated_at=now()"""),{"id":fid,"t":UUID(auth.tenant_id),"n":req.name,"v":req.version,"s":req.source,"d":req.data_type,"def":json.dumps(req.definition),"st":req.status})
    return {"feature_id":str(fid),"status":req.status}

@router.post("/datasets",status_code=201)
async def create_dataset(req:DatasetRequest, auth:AuthContext=Depends(get_auth_context), session=Depends(get_tenant_session)):
    did=uuid4(); await session.execute(text("""INSERT INTO ml_dataset_snapshots(dataset_id,tenant_id,name,version,source_query_hash,feature_ids,row_count,schema_hash,content_hash,split) VALUES(:id,:t,:n,:v,:q,:f,:r,:s,:c,CAST(:sp AS jsonb)) ON CONFLICT(tenant_id,name,version) DO NOTHING"""),{"id":did,"t":UUID(auth.tenant_id),"n":req.name,"v":req.version,"q":req.source_query_hash.lower(),"f":[str(x) for x in req.feature_ids],"r":req.row_count,"s":req.schema_hash.lower(),"c":req.content_hash.lower(),"sp":json.dumps(req.split)})
    return {"dataset_id":str(did),"status":"created"}

@router.post("/training-runs",status_code=201)
async def create_training(req:TrainingRequest, auth:AuthContext=Depends(get_auth_context), session=Depends(get_tenant_session)):
    tid=uuid4(); await session.execute(text("""INSERT INTO ml_training_runs(training_id,tenant_id,dataset_id,model_name,candidate_version,framework,algorithm,hyperparameters) VALUES(:id,:t,:d,:n,:v,:f,:a,CAST(:h AS jsonb))"""),{"id":tid,"t":UUID(auth.tenant_id),"d":req.dataset_id,"n":req.model_name,"v":req.candidate_version,"f":req.framework,"a":req.algorithm,"h":json.dumps(req.hyperparameters)})
    return {"training_id":str(tid),"status":"queued"}

@router.post("/evaluations",status_code=201)
async def create_evaluation(req:EvaluationRequest, auth:AuthContext=Depends(get_auth_context), session=Depends(get_tenant_session)):
    result=evaluation_gate(req.model_dump(),min_score=req.min_score,max_false_positive_rate=req.max_false_positive_rate)
    eid=uuid4(); metrics={"primary_score":req.primary_score,"false_positive_rate":req.false_positive_rate,"min_score":req.min_score,"max_false_positive_rate":req.max_false_positive_rate}
    await session.execute(text("""INSERT INTO ml_model_evaluations(evaluation_id,tenant_id,training_id,model_id,gate,passed,metrics,evaluator) VALUES(:id,:t,:tr,:m,:g,:p,CAST(:x AS jsonb),:e)"""),{"id":eid,"t":UUID(auth.tenant_id),"tr":req.training_id,"m":req.model_id,"g":req.gate,"p":result.passed,"x":json.dumps(metrics),"e":req.evaluator})
    return {"evaluation_id":str(eid),"passed":result.passed,"reason":result.reason}

@router.post("/drift",status_code=201)
async def record_drift(req:DriftRequest, auth:AuthContext=Depends(get_auth_context), session=Depends(get_tenant_session)):
    action=drift_action(req.value,req.threshold); did=uuid4(); detected=action!='observe'
    await session.execute(text("""INSERT INTO ml_drift_metrics(drift_id,tenant_id,model_id,feature_name,metric,value,threshold,detected,window_start,window_end,action) VALUES(:id,:t,:m,:f,:me,:v,:th,:d,CAST(CAST(:ws AS text) AS timestamptz),CAST(CAST(:we AS text) AS timestamptz),:a)"""),{"id":did,"t":UUID(auth.tenant_id),"m":req.model_id,"f":req.feature_name,"me":req.metric,"v":req.value,"th":req.threshold,"d":detected,"ws":req.window_start,"we":req.window_end,"a":action})
    return {"drift_id":str(did),"action":action,"detected":detected}

@router.post("/deployments",status_code=201)
async def create_deployment(req:PromotionRequest, auth:AuthContext=Depends(get_auth_context), session=Depends(get_tenant_session)):
    row=(await session.execute(text("SELECT approved_for_inference FROM neural_model_registry WHERE model_id=:m AND tenant_id=:t"),{"m":req.model_id,"t":UUID(auth.tenant_id)})).first()
    if not row: raise HTTPException(404,"MODEL_NOT_FOUND")
    allowed=deployment_allowed(model_approved=bool(row[0]),evaluation_passed=req.evaluation_passed,artifact_verified=req.artifact_verified)
    did=uuid4(); state='active' if allowed else 'pending'; rollout=100 if allowed else 0
    await session.execute(text("""INSERT INTO ml_deployments(deployment_id,tenant_id,model_id,environment,state,rollout_percent,reason) VALUES(:id,:t,:m,:e,:s,:r,:reason)"""),{"id":did,"t":UUID(auth.tenant_id),"m":req.model_id,"e":req.environment,"s":state,"r":rollout,"reason":req.reason or ('promotion gates passed' if allowed else 'promotion gates not passed')})
    return {"deployment_id":str(did),"allowed":allowed,"state":state,"rollout_percent":rollout}
