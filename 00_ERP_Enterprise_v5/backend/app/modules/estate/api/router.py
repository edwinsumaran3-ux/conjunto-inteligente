import hashlib, json
from datetime import datetime
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session

router=APIRouter(prefix='/estate',tags=['estate'])

PROPERTY_TYPES={
 'residential_complex','building','housing_block','house','farm','rural_property','condominium',
 'gated_community','parcel','mixed_use','commercial','industrial','institutional','hospitality',
 'parking_facility','construction_site','campus','other'
}

class PropertyIn(BaseModel):
    root_node_id: UUID
    property_type: str=Field(min_length=1,max_length=48)
    code: str=Field(min_length=1,max_length=160)
    name: str=Field(min_length=1,max_length=240)
    country_code: str|None=Field(default=None,min_length=2,max_length=2)
    region: str|None=Field(default=None,max_length=120)
    city: str|None=Field(default=None,max_length=160)
    address_line: str|None=Field(default=None,max_length=300)
    postal_code: str|None=Field(default=None,max_length=32)
    cadastral_reference: str|None=Field(default=None,max_length=180)
    timezone: str=Field(default='America/Bogota',max_length=64)
    metadata: dict=Field(default_factory=dict)

class UnitIn(BaseModel):
    property_id: UUID
    node_id: UUID
    unit_type: str=Field(min_length=1,max_length=48)
    code: str=Field(min_length=1,max_length=160)
    name: str=Field(min_length=1,max_length=240)
    occupancy_status: str='unknown'
    area_m2: float|None=Field(default=None,ge=0)
    metadata: dict=Field(default_factory=dict)

class EventIn(BaseModel):
    event_type: str=Field(min_length=1,max_length=96)
    severity: str='info'
    source_type: str=Field(min_length=1,max_length=48)
    source_id: UUID|None=None
    property_id: UUID|None=None
    node_id: UUID|None=None
    correlation_id: str|None=Field(default=None,max_length=128)
    idempotency_key: str=Field(min_length=1,max_length=220)
    observed_at: datetime
    payload: dict=Field(default_factory=dict)
    evidence: list=Field(default_factory=list)

class EventActionIn(BaseModel):
    event_id: UUID
    actor_type: str
    actor_id: str=Field(min_length=1,max_length=160)
    action: str=Field(min_length=1,max_length=96)
    requires_human_approval: bool=True
    approval_id: UUID|None=None
    idempotency_key: str=Field(min_length=1,max_length=220)
    payload: dict=Field(default_factory=dict)

@router.get('/catalog')
async def catalog():
    return {'property_types':sorted(PROPERTY_TYPES),'principle':'The topology is not limited to buildings; any managed physical estate can be represented as a root with nested nodes, units, assets and devices.'}

@router.post('/properties',status_code=201)
async def create_property(body:PropertyIn,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    if body.property_type not in PROPERTY_TYPES: raise HTTPException(422,'property_type no soportado')
    root=await session.scalar(text('SELECT 1 FROM twin_nodes WHERE tenant_id=:t AND id=:id'),{'t':UUID(auth.tenant_id),'id':body.root_node_id})
    if not root: raise HTTPException(422,'root_node_id no pertenece al tenant')
    try:
        row=(await session.execute(text("""INSERT INTO managed_properties(tenant_id,root_node_id,property_type,code,name,country_code,region,city,address_line,postal_code,cadastral_reference,timezone,metadata)
        VALUES(:t,:r,:pt,:c,:n,:cc,:rg,:ci,:ad,:pc,:cr,:tz,CAST(:md AS jsonb)) RETURNING id"""),{
            't':UUID(auth.tenant_id),'r':body.root_node_id,'pt':body.property_type,'c':body.code,'n':body.name,'cc':body.country_code,
            'rg':body.region,'ci':body.city,'ad':body.address_line,'pc':body.postal_code,'cr':body.cadastral_reference,'tz':body.timezone,'md':json.dumps(body.metadata)})).scalar_one()
    except Exception as exc: raise HTTPException(409,'property code/root already exists') from exc
    return {'id':str(row),'status':'created'}

@router.get('/properties')
async def list_properties(auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    rows=(await session.execute(text("SELECT id,root_node_id,property_type,code,name,country_code,region,city,address_line,postal_code,cadastral_reference,timezone,active,metadata,created_at,updated_at FROM managed_properties WHERE tenant_id=:t ORDER BY name"),{'t':UUID(auth.tenant_id)})).mappings().all()
    return [dict(r) for r in rows]

@router.post('/units',status_code=201)
async def create_unit(body:UnitIn,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    valid=await session.scalar(text('SELECT 1 FROM managed_properties WHERE tenant_id=:t AND id=:p'),{'t':UUID(auth.tenant_id),'p':body.property_id})
    node=await session.scalar(text('SELECT 1 FROM twin_nodes WHERE tenant_id=:t AND id=:n'),{'t':UUID(auth.tenant_id),'n':body.node_id})
    if not valid or not node: raise HTTPException(422,'property_id y node_id deben pertenecer al tenant')
    try:
        row=(await session.execute(text("""INSERT INTO managed_units(tenant_id,property_id,node_id,unit_type,code,name,occupancy_status,area_m2,metadata)
        VALUES(:t,:p,:n,:ut,:c,:nm,:os,:a,CAST(:md AS jsonb)) RETURNING id"""),{'t':UUID(auth.tenant_id),'p':body.property_id,'n':body.node_id,'ut':body.unit_type,'c':body.code,'nm':body.name,'os':body.occupancy_status,'a':body.area_m2,'md':json.dumps(body.metadata)})).scalar_one()
    except Exception as exc: raise HTTPException(409,'unit code/node already exists or violates a constraint') from exc
    return {'id':str(row),'status':'created'}

@router.get('/events')
async def list_events(limit:int=Query(100,ge=1,le=500),status:str|None=None,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    q='SELECT id,event_type,severity,status,source_type,source_id,property_id,node_id,correlation_id,idempotency_key,observed_at,payload,evidence,created_at,updated_at FROM operational_events WHERE tenant_id=:t'
    p={'t':UUID(auth.tenant_id),'limit':limit}
    if status: q+=' AND status=:s'; p['s']=status
    q+=' ORDER BY observed_at DESC LIMIT :limit'
    return [dict(x) for x in (await session.execute(text(q),p)).mappings().all()]

@router.post('/events',status_code=201)
async def ingest_event(body:EventIn,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    raw=json.dumps(body.payload,sort_keys=True,separators=(',',':'),default=str).encode(); digest=hashlib.sha256(raw).hexdigest()
    if body.property_id and not await session.scalar(text('SELECT 1 FROM managed_properties WHERE tenant_id=:t AND id=:id'),{'t':UUID(auth.tenant_id),'id':body.property_id}): raise HTTPException(422,'property_id no pertenece al tenant')
    if body.node_id and not await session.scalar(text('SELECT 1 FROM twin_nodes WHERE tenant_id=:t AND id=:id'),{'t':UUID(auth.tenant_id),'id':body.node_id}): raise HTTPException(422,'node_id no pertenece al tenant')
    try:
        row=(await session.execute(text("""INSERT INTO operational_events(tenant_id,event_type,severity,source_type,source_id,property_id,node_id,correlation_id,idempotency_key,observed_at,payload,evidence)
        VALUES(:t,:et,:sv,:st,:sid,:p,:n,:c,:ik,:o,CAST(:pl AS jsonb),CAST(:ev AS jsonb)) RETURNING id"""),{'t':UUID(auth.tenant_id),'et':body.event_type,'sv':body.severity,'st':body.source_type,'sid':body.source_id,'p':body.property_id,'n':body.node_id,'c':body.correlation_id,'ik':body.idempotency_key,'o':body.observed_at,'pl':json.dumps(body.payload),'ev':json.dumps(body.evidence)})).scalar_one()
    except Exception as exc:
        existing=await session.scalar(text('SELECT id FROM operational_events WHERE tenant_id=:t AND idempotency_key=:ik'),{'t':UUID(auth.tenant_id),'ik':body.idempotency_key})
        if existing: return {'id':str(existing),'status':'duplicate','input_hash':digest}
        raise HTTPException(409,'event violates an integrity constraint') from exc
    return {'id':str(row),'status':'accepted','input_hash':digest}

@router.post('/event-actions',status_code=201)
async def record_action(body:EventActionIn,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    exists=await session.scalar(text('SELECT 1 FROM operational_events WHERE tenant_id=:t AND id=:id'),{'t':UUID(auth.tenant_id),'id':body.event_id})
    if not exists: raise HTTPException(404,'event not found')
    if body.requires_human_approval and not body.approval_id:
        status='awaiting_approval'
    else: status='accepted'
    raw=json.dumps(body.payload,sort_keys=True,separators=(',',':'),default=str).encode(); digest=hashlib.sha256(raw).hexdigest()
    try:
        row=(await session.execute(text("""INSERT INTO event_actions(tenant_id,event_id,actor_type,actor_id,action,status,requires_human_approval,approval_id,idempotency_key,input_hash,result)
        VALUES(:t,:e,:at,:ai,:a,:s,:r,:ap,:ik,:h,CAST(:res AS jsonb)) RETURNING id"""),{'t':UUID(auth.tenant_id),'e':body.event_id,'at':body.actor_type,'ai':body.actor_id,'a':body.action,'s':status,'r':body.requires_human_approval,'ap':body.approval_id,'ik':body.idempotency_key,'h':digest,'res':json.dumps({'accepted':status=='accepted'})})).scalar_one()
    except Exception as exc:
        existing=await session.scalar(text('SELECT id,status FROM event_actions WHERE tenant_id=:t AND idempotency_key=:ik'),{'t':UUID(auth.tenant_id),'ik':body.idempotency_key})
        if existing: return {'id':str(existing[0]),'status':'duplicate'}
        raise HTTPException(409,'action violates an integrity constraint') from exc
    return {'id':str(row),'status':status,'input_hash':digest}
