from __future__ import annotations
import json
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session
from .service import FeaturePoint, rolling_features, canonical_hash, governed_decision

router=APIRouter(prefix='/intelligence',tags=['intelligence-plane'])
class FeatureRequest(BaseModel):
    node_id: UUID; feature_name: str=Field(min_length=1,max_length=160); feature_version: str=Field(min_length=1,max_length=32)
    source: str=Field(min_length=1,max_length=160); window_start: datetime|None=None; window_end: datetime|None=None
class NeuralDecisionRequest(BaseModel):
    request_id: str=Field(min_length=1,max_length=128); agent: str=Field(min_length=1,max_length=160); purpose: str=Field(min_length=1,max_length=160)
    model_id: UUID; node_id: UUID|None=None; proposed_decision: str=Field(min_length=1,max_length=64); confidence: float=Field(ge=0,le=1)
    input_payload: dict; environment: str='production'

@router.post('/features/from-telemetry')
async def features(body:FeatureRequest,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    tenant=UUID(auth.tenant_id)
    rows=(await session.execute(text("""SELECT value_double,observed_at FROM twin_telemetry WHERE tenant_id=:t AND node_id=:n AND observed_at>=COALESCE(:ws, '-infinity'::timestamptz) AND observed_at<=COALESCE(:we, 'infinity'::timestamptz) ORDER BY observed_at"""),{'t':tenant,'n':body.node_id,'ws':body.window_start,'we':body.window_end})).mappings().all()
    if not rows: raise HTTPException(404,'NO_TELEMETRY_FOR_FEATURE_WINDOW')
    points=[FeaturePoint(body.feature_name,float(r['value_double']),r['observed_at']) for r in rows]
    values=rolling_features(points)
    out=[]
    for name,value in values.items():
        feature=f'{body.feature_name}.{name}'
        row=(await session.execute(text("""INSERT INTO ml_feature_observations(tenant_id,node_id,feature_name,feature_version,value_double,observed_at,source,window_start,window_end,quality) VALUES(:t,:n,:f,:v,:x,:o,:s,:ws,:we,'good') RETURNING observation_id"""),{'t':tenant,'n':body.node_id,'f':feature,'v':body.feature_version,'x':value,'o':rows[-1]['observed_at'],'s':body.source,'ws':body.window_start,'we':body.window_end})).scalar_one()
        out.append({'observation_id':str(row),'feature':feature,'value':value})
    return {'node_id':str(body.node_id),'features':out}

@router.post('/neural/decision')
async def neural_decision(body:NeuralDecisionRequest,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    tenant=UUID(auth.tenant_id)
    policy=(await session.execute(text("SELECT policy_id,model_id,min_confidence,allowed_decisions,enabled FROM agent_neural_policies WHERE tenant_id=:t AND agent=:a AND purpose=:p AND environment=:e"),{'t':tenant,'a':body.agent,'p':body.purpose,'e':body.environment})).mappings().first()
    if not policy: raise HTTPException(404,'NEURAL_POLICY_NOT_FOUND')
    model=(await session.execute(text("SELECT approved_for_inference FROM neural_model_registry WHERE tenant_id=:t AND model_id=:m AND status='validated'"),{'t':tenant,'m':body.model_id})).scalar_one_or_none()
    route=(await session.execute(text("SELECT 1 FROM ml_inference_routes WHERE tenant_id=:t AND model_id=:m AND environment=:e AND active=true AND traffic_percent>0 LIMIT 1"),{'t':tenant,'m':body.model_id,'e':body.environment})).scalar_one_or_none()
    decision,reason=governed_decision(proposed=body.proposed_decision,confidence=body.confidence,min_confidence=float(policy['min_confidence']),allowed=set(policy['allowed_decisions']),model_approved=bool(model),route_active=bool(route and policy['enabled'] and body.model_id==policy['model_id']))
    status='accepted' if reason=='GOVERNED_RECOMMENDATION' else 'rejected'
    inp=canonical_hash(body.input_payload); out=canonical_hash({'decision':decision,'confidence':body.confidence,'reason':reason})
    await session.execute(text("""INSERT INTO agent_neural_invocations(tenant_id,request_id,agent,purpose,model_id,node_id,input_hash,output_hash,decision,confidence,status,reason) VALUES(:t,:r,:a,:p,:m,:n,:i,:o,:d,:c,:s,:reason) ON CONFLICT(tenant_id,request_id) DO NOTHING"""),{'t':tenant,'r':body.request_id,'a':body.agent,'p':body.purpose,'m':body.model_id,'n':body.node_id,'i':inp,'o':out,'d':decision,'c':body.confidence,'s':status,'reason':reason})
    await session.commit()
    return {'request_id':body.request_id,'decision':decision,'confidence':body.confidence,'status':status,'reason':reason,'execution_required': decision!='observe'}
