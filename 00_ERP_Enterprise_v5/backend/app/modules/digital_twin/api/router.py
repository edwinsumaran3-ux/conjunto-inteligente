import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session
from backend.app.core.outbox import enqueue
from backend.app.modules.digital_twin.domain.sensor_simulator import generate_readings, get_profile, profile_catalog

router=APIRouter(prefix='/digital-twin',tags=['digital-twin'])

class NodeIn(BaseModel):
    parent_id: UUID|None=None; node_type: str=Field(min_length=1,max_length=40); code: str=Field(min_length=1,max_length=160)
    name: str=Field(min_length=1,max_length=240); status: str=Field(default='unknown',min_length=1,max_length=32)
    latitude: float|None=Field(default=None,ge=-90,le=90); longitude: float|None=Field(default=None,ge=-180,le=180); elevation_m: float|None=None; metadata: dict = Field(default_factory=dict)
class EdgeIn(BaseModel):
    from_node: UUID; to_node: UUID; relation: str=Field(min_length=1,max_length=60); metadata: dict=Field(default_factory=dict)


class ModelVersionIn(BaseModel):
    model_key: str = Field(min_length=1,max_length=180)
    version: str = Field(min_length=1,max_length=80)
    source_system: str = Field(min_length=1,max_length=120)
    source_format: str = Field(min_length=1,max_length=40)
    lifecycle_status: str = Field(default='DRAFT',max_length=32)
    schema_uri: str|None = Field(default=None,max_length=500)
    source_revision: str|None = Field(default=None,max_length=180)
    document_ref: str|None = Field(default=None,max_length=500)
    content_sha256: str|None = Field(default=None,max_length=64)
    metadata: dict = Field(default_factory=dict)

class BindingIn(BaseModel):
    node_id: UUID
    model_version_id: UUID|None = None
    identifier_system: str = Field(min_length=1,max_length=80)
    identifier_type: str = Field(min_length=1,max_length=80)
    identifier: str = Field(min_length=1,max_length=240)
    provenance_id: UUID|None = None
    confidence: float = Field(default=1.0,ge=0,le=1)
    metadata: dict = Field(default_factory=dict)

class PropertyIn(BaseModel):
    node_id: UUID
    model_version_id: UUID|None = None
    provenance_id: UUID|None = None
    namespace: str = Field(min_length=1,max_length=160)
    property_name: str = Field(min_length=1,max_length=180)
    value_type: str = Field(min_length=1,max_length=40)
    value: object
    unit: str|None = Field(default=None,max_length=40)
    source: str = Field(min_length=1,max_length=160)
    quality: str = Field(default='VALID',max_length=32)
    effective_from: datetime|None = None
    effective_to: datetime|None = None
    observed_at: datetime|None = None

class SpatialReferenceIn(BaseModel):
    node_id: UUID
    model_version_id: UUID|None = None
    reference_system: str = Field(min_length=1,max_length=120)
    geometry_type: str = Field(default='POINT',max_length=40)
    geometry: dict
    floor_ref: str|None = Field(default=None,max_length=120)
    space_ref: str|None = Field(default=None,max_length=240)
    elevation_m: float|None = None
    provenance_id: UUID|None = None
    confidence: float = Field(default=1.0,ge=0,le=1)

class SnapshotIn(BaseModel):
    node_id: UUID
    model_version_id: UUID|None = None
    state: str = Field(default='UNKNOWN',max_length=40)
    health_score: float|None = Field(default=None,ge=0,le=100)
    confidence: float = Field(default=1.0,ge=0,le=1)
    state_data: dict = Field(default_factory=dict)
    derived_from: list = Field(default_factory=list)

class TelemetryIn(BaseModel):
    node_id: UUID; metric: str=Field(min_length=1,max_length=120); value_double: float; unit: str|None=Field(default=None,max_length=32)
    quality: str=Field(default='good',min_length=1,max_length=24); observed_at: datetime; source: str=Field(min_length=1,max_length=120)
    correlation_id: str|None=Field(default=None,max_length=128); metadata: dict=Field(default_factory=dict)

@router.get('/graph')
async def graph(auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    nodes=(await session.execute(text("SELECT id,parent_id,node_type,code,name,status,latitude,longitude,elevation_m,metadata,created_at,updated_at FROM twin_nodes WHERE tenant_id=:t ORDER BY node_type,code"),{'t':UUID(auth.tenant_id)})).mappings().all()
    edges=(await session.execute(text("SELECT id,from_node,to_node,relation,metadata,created_at FROM twin_edges WHERE tenant_id=:t ORDER BY created_at"),{'t':UUID(auth.tenant_id)})).mappings().all()
    return {'nodes':[dict(x) for x in nodes],'edges':[dict(x) for x in edges]}

@router.get('/nodes')
async def list_nodes(
    limit:int=Query(100,ge=1,le=500),
    offset:int=Query(0,ge=0),
    search:str|None=Query(None,max_length=160),
    node_type:str|None=Query(None,max_length=40),
    auth:AuthContext=Depends(get_auth_context),
    session:AsyncSession=Depends(get_tenant_session),
):
    tenant=UUID(auth.tenant_id)
    filters=["n.tenant_id=:t"]
    params={'t':tenant,'limit':limit,'offset':offset}
    if search:
        filters.append("(n.name ILIKE :search OR n.code ILIKE :search)")
        params['search']=f"%{search}%"
    if node_type:
        filters.append("n.node_type=:node_type")
        params['node_type']=node_type
    where=" AND ".join(filters)
    total=await session.scalar(text(f"SELECT count(*) FROM twin_nodes n WHERE {where}"),params)
    items=(await session.execute(text(f"""
        SELECT n.id,n.parent_id,p.name parent_name,n.node_type,n.code,n.name,n.status,
               n.latitude,n.longitude,n.elevation_m,n.metadata,n.created_at,n.updated_at
        FROM twin_nodes n
        LEFT JOIN twin_nodes p ON p.tenant_id=n.tenant_id AND p.id=n.parent_id
        WHERE {where}
        ORDER BY n.node_type,n.name,n.code,n.id
        LIMIT :limit OFFSET :offset
    """),params)).mappings().all()
    return {'items':[dict(row) for row in items],'total':total or 0,'limit':limit,'offset':offset}

@router.post('/nodes',status_code=201)
async def create_node(body:NodeIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    if body.parent_id:
        exists=await session.scalar(text('SELECT 1 FROM twin_nodes WHERE tenant_id=:t AND id=:id'),{'t':UUID(auth.tenant_id),'id':body.parent_id})
        if not exists: raise HTTPException(422,'parent_id no pertenece al tenant')
    try:
        row=(await session.execute(text("""INSERT INTO twin_nodes(tenant_id,parent_id,node_type,code,name,status,latitude,longitude,elevation_m,metadata) VALUES(:t,:p,:ty,:c,:n,:s,:lat,:lon,:e,CAST(:m AS jsonb)) RETURNING id"""),{'t':UUID(auth.tenant_id),'p':body.parent_id,'ty':body.node_type,'c':body.code,'n':body.name,'s':body.status,'lat':body.latitude,'lon':body.longitude,'e':body.elevation_m,'m':__import__('json').dumps(body.metadata)})).scalar_one()
    except Exception as exc: raise HTTPException(409,'node code already exists or violates a graph constraint') from exc
    return {'id':str(row),'status':'created'}

@router.post('/edges',status_code=201)
async def create_edge(body:EdgeIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    if body.from_node==body.to_node: raise HTTPException(422,'self edge is not allowed')
    count=await session.scalar(text('SELECT count(*) FROM twin_nodes WHERE tenant_id=:t AND id IN (:a,:b)'),{'t':UUID(auth.tenant_id),'a':body.from_node,'b':body.to_node})
    if count!=2: raise HTTPException(422,'both nodes must belong to the tenant')
    try:
        row=(await session.execute(text("INSERT INTO twin_edges(tenant_id,from_node,to_node,relation,metadata) VALUES(:t,:a,:b,:r,CAST(:m AS jsonb)) RETURNING id"),{'t':UUID(auth.tenant_id),'a':body.from_node,'b':body.to_node,'r':body.relation,'m':__import__('json').dumps(body.metadata)})).scalar_one()
    except Exception as exc: raise HTTPException(409,'edge already exists or violates a graph constraint') from exc
    return {'id':str(row),'status':'created'}

@router.post('/telemetry',status_code=201)
async def ingest_telemetry(body:TelemetryIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    exists=await session.scalar(text('SELECT 1 FROM twin_nodes WHERE tenant_id=:t AND id=:id'),{'t':UUID(auth.tenant_id),'id':body.node_id})
    if not exists: raise HTTPException(404,'twin node not found')
    row=(await session.execute(text("""INSERT INTO twin_telemetry(tenant_id,node_id,metric,value_double,unit,quality,observed_at,source,correlation_id,metadata) VALUES(:t,:n,:m,:v,:u,:q,:o,:s,:c,CAST(:md AS jsonb)) RETURNING id"""),{'t':UUID(auth.tenant_id),'n':body.node_id,'m':body.metric,'v':body.value_double,'u':body.unit,'q':body.quality,'o':body.observed_at,'s':body.source,'c':body.correlation_id,'md':__import__('json').dumps(body.metadata)})).scalar_one()
    return {'id':row,'status':'accepted'}



@router.post('/model-versions',status_code=201)
async def create_model_version(body:ModelVersionIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    import json
    row=(await session.execute(text("""INSERT INTO twin_model_versions(tenant_id,model_key,version,source_system,source_format,lifecycle_status,schema_uri,source_revision,document_ref,content_sha256,metadata) VALUES(:t,:k,:v,:ss,:sf,:ls,:su,:sr,:dr,:sha,CAST(:m AS jsonb)) RETURNING id"""),{'t':UUID(auth.tenant_id),'k':body.model_key,'v':body.version,'ss':body.source_system,'sf':body.source_format,'ls':body.lifecycle_status,'su':body.schema_uri,'sr':body.source_revision,'dr':body.document_ref,'sha':body.content_sha256,'m':json.dumps(body.metadata)})).scalar_one()
    return {'id':str(row),'status':'created'}

@router.post('/bindings',status_code=201)
async def create_binding(body:BindingIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    import json
    exists=await session.scalar(text('SELECT 1 FROM twin_nodes WHERE tenant_id=:t AND id=:id'),{'t':UUID(auth.tenant_id),'id':body.node_id})
    if not exists: raise HTTPException(404,'twin node not found')
    row=(await session.execute(text("""INSERT INTO twin_bindings(tenant_id,node_id,model_version_id,identifier_system,identifier_type,identifier,provenance_id,confidence,metadata) VALUES(:t,:n,:mv,:isys,:itype,:i,:p,:c,CAST(:m AS jsonb)) RETURNING id"""),{'t':UUID(auth.tenant_id),'n':body.node_id,'mv':body.model_version_id,'isys':body.identifier_system,'itype':body.identifier_type,'i':body.identifier,'p':body.provenance_id,'c':body.confidence,'m':json.dumps(body.metadata)})).scalar_one()
    return {'id':str(row),'status':'created'}

@router.post('/spatial-references',status_code=201)
async def create_spatial_reference(body:SpatialReferenceIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    import json
    row=(await session.execute(text("""INSERT INTO twin_spatial_references(tenant_id,node_id,model_version_id,reference_system,geometry_type,geometry,floor_ref,space_ref,elevation_m,provenance_id,confidence) VALUES(:t,:n,:mv,:rs,:gt,CAST(:g AS jsonb),:f,:s,:e,:p,:c) RETURNING id"""),{'t':UUID(auth.tenant_id),'n':body.node_id,'mv':body.model_version_id,'rs':body.reference_system,'gt':body.geometry_type,'g':json.dumps(body.geometry),'f':body.floor_ref,'s':body.space_ref,'e':body.elevation_m,'p':body.provenance_id,'c':body.confidence})).scalar_one()
    return {'id':str(row),'status':'created'}

@router.post('/properties',status_code=201)
async def create_property(body:PropertyIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    import json
    row=(await session.execute(text("""INSERT INTO twin_properties(tenant_id,node_id,model_version_id,provenance_id,namespace,property_name,value_type,value,unit,source,quality,effective_from,effective_to,observed_at) VALUES(:t,:n,:mv,:p,:ns,:pn,:vt,CAST(:v AS jsonb),:u,:s,:q,:ef,:et,:o) RETURNING id"""),{'t':UUID(auth.tenant_id),'n':body.node_id,'mv':body.model_version_id,'p':body.provenance_id,'ns':body.namespace,'pn':body.property_name,'vt':body.value_type,'v':json.dumps(body.value),'u':body.unit,'s':body.source,'q':body.quality,'ef':body.effective_from,'et':body.effective_to,'o':body.observed_at})).scalar_one()
    return {'id':str(row),'status':'created'}

@router.post('/snapshots',status_code=201)
async def create_snapshot(body:SnapshotIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    import json
    row=(await session.execute(text("""INSERT INTO twin_state_snapshots(tenant_id,node_id,model_version_id,state,state_data,health_score,confidence,derived_from) VALUES(:t,:n,:mv,:st,CAST(:sd AS jsonb),:h,:c,CAST(:df AS jsonb)) RETURNING id,captured_at"""),{'t':UUID(auth.tenant_id),'n':body.node_id,'mv':body.model_version_id,'st':body.state,'sd':json.dumps(body.state_data),'h':body.health_score,'c':body.confidence,'df':json.dumps(body.derived_from)})).one()
    return {'id':str(row[0]),'captured_at':row[1],'status':'created'}

@router.get('/nodes/{node_id}/telemetry')
async def node_telemetry(node_id:UUID,limit:int=Query(100,ge=1,le=1000),auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    rows=(await session.execute(text("SELECT id,metric,value_double,unit,quality,observed_at,source,correlation_id,metadata FROM twin_telemetry WHERE tenant_id=:t AND node_id=:n ORDER BY observed_at DESC LIMIT :limit"),{'t':UUID(auth.tenant_id),'n':node_id,'limit':limit})).mappings().all()
    return [dict(x) for x in rows]

class DeviceIn(BaseModel):
    node_id: UUID|None = None
    external_device_id: str|None = Field(default=None,max_length=200)
    device_type: str = Field(min_length=1,max_length=80)
    manufacturer: str|None = Field(default=None,max_length=160)
    model: str|None = Field(default=None,max_length=160)
    serial_number: str|None = Field(default=None,max_length=160)
    firmware_version: str|None = Field(default=None,max_length=120)
    protocol: str|None = Field(default=None,max_length=80)
    metadata: dict = Field(default_factory=dict)

class PointIn(BaseModel):
    node_id: UUID
    device_id: UUID|None = None
    code: str = Field(min_length=1,max_length=180)
    name: str = Field(min_length=1,max_length=240)
    semantic_kind: str = Field(min_length=1,max_length=100)
    data_type: str = Field(default='float64',max_length=40)
    canonical_unit: str|None = Field(default=None,max_length=40)
    engineering_min: float|None = None
    engineering_max: float|None = None
    stale_after_seconds: int = Field(default=300,gt=0,le=604800)
    sampling_interval_seconds: int|None = Field(default=None,gt=0)
    metadata: dict = Field(default_factory=dict)

class TelemetrySampleIn(BaseModel):
    point_id: UUID
    value: float = Field(allow_inf_nan=False)
    unit: str|None = Field(default=None,max_length=40)
    observed_at: datetime
    source: str = Field(min_length=1,max_length=160)
    source_message_id: str|None = Field(default=None,max_length=240)
    sequence: int|None = Field(default=None,ge=0)
    source_quality: str = Field(default='GOOD',max_length=32)
    correlation_id: str|None = Field(default=None,max_length=128)
    metadata: dict = Field(default_factory=dict)


class TelemetryBatchIn(BaseModel):
    samples: list[TelemetrySampleIn] = Field(min_length=1,max_length=500)


class SimulatedDeviceIn(BaseModel):
    node_id: UUID
    profile_id: str = Field(min_length=1,max_length=80)
    code: str = Field(min_length=1,max_length=180)
    name: str|None = Field(default=None,min_length=1,max_length=240)


class SimulationRunIn(BaseModel):
    run_id: UUID
    scenario: str = Field(pattern='^(normal|alarm)$')


def _telemetry_payload_hash(body:TelemetrySampleIn,observed:datetime)->str:
    import hashlib, json
    payload={
        'point_id':str(body.point_id),'value':body.value,'unit':body.unit,
        'observed_at':observed.isoformat(),'source':body.source,
        'sequence':body.sequence,'metadata':body.metadata,
    }
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()


async def _ingest_operational_batch(
    body:TelemetryBatchIn,
    auth:AuthContext,
    session:AsyncSession,
)->dict:
    import json
    from backend.app.modules.digital_twin.domain.operational_telemetry import normalize_measurement, classify_quality

    tenant=UUID(auth.tenant_id)
    if any(not sample.source_message_id for sample in body.samples):
        raise HTTPException(422,'BATCH_SAMPLE_SOURCE_MESSAGE_ID_REQUIRED')

    point_ids=list(dict.fromkeys(sample.point_id for sample in body.samples))
    point_parameters={'t':tenant}
    point_placeholders=[]
    for index,point_id in enumerate(point_ids):
        key=f'point_{index}'
        point_parameters[key]=point_id
        point_placeholders.append(f':{key}')
    points=(await session.execute(text(f"""
        SELECT id,node_id,device_id,canonical_unit,engineering_min,engineering_max,stale_after_seconds
        FROM twin_points WHERE tenant_id=:t AND id IN ({', '.join(point_placeholders)})
    """),point_parameters)).mappings().all()
    point_by_id={row['id']:row for row in points}
    missing=set(point_ids)-set(point_by_id)
    if missing:
        raise HTTPException(404,'TWIN_POINT_NOT_FOUND')

    now=datetime.now(timezone.utc)
    prepared=[]
    batch_hashes={}
    original_indexes={}
    for index,sample in enumerate(body.samples):
        point=point_by_id[sample.point_id]
        observed=sample.observed_at if sample.observed_at.tzinfo else sample.observed_at.replace(tzinfo=timezone.utc)
        try:
            normalized=normalize_measurement(sample.value,sample.unit,point['canonical_unit'])
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from exc
        quality,reason=classify_quality(
            observed_at=observed,received_at=now,source_quality=sample.source_quality,
            value=normalized.canonical_value,engineering_min=point['engineering_min'],
            engineering_max=point['engineering_max'],stale_after_seconds=point['stale_after_seconds'],
        )
        payload_hash=_telemetry_payload_hash(sample,observed)
        message_id=sample.source_message_id
        previous_hash=batch_hashes.get(message_id)
        if previous_hash is not None and previous_hash!=payload_hash:
            raise HTTPException(409,'BATCH_MESSAGE_ID_REUSED_WITH_DIFFERENT_PAYLOAD')
        batch_hashes[message_id]=payload_hash
        original_indexes.setdefault(message_id,index)
        prepared.append({
            'tenant_id':tenant,'point_id':sample.point_id,'device_id':point['device_id'],
            'observed_at':observed,'received_at':now,'sequence':sample.sequence,
            'source_message_id':message_id,'source':sample.source,
            'raw_value':sample.value,'raw_unit':sample.unit,
            'canonical_value':normalized.canonical_value,'canonical_unit':normalized.canonical_unit,
            'quality':quality,'quality_reason':reason,'correlation_id':sample.correlation_id,
            'payload_hash':payload_hash,'metadata':json.dumps(sample.metadata),
            'unit':normalized.canonical_unit,'original_index':index,
        })

    unique_messages=list(batch_hashes)
    message_parameters={'t':tenant}
    message_placeholders=[]
    for index,message_id in enumerate(unique_messages):
        key=f'message_{index}'
        message_parameters[key]=message_id
        message_placeholders.append(f':{key}')
    existing=(await session.execute(text(f"""
        SELECT source_message_id,payload_hash
        FROM twin_telemetry_samples
        WHERE tenant_id=:t AND source_message_id IN ({', '.join(message_placeholders)})
    """),message_parameters)).mappings().all()
    existing_hashes={row['source_message_id']:row['payload_hash'] for row in existing}
    for message_id,stored_hash in existing_hashes.items():
        if stored_hash!=batch_hashes[message_id]:
            raise HTTPException(409,'TELEMETRY_MESSAGE_ID_CONFLICT')

    unique_prepared={}
    for item in prepared:
        message_id=item['source_message_id']
        if message_id not in existing_hashes:
            unique_prepared.setdefault(message_id,item)
    insert_items=list(unique_prepared.values())
    inserted_by_message={}
    if insert_items:
        columns=(
            'tenant_id','point_id','device_id','observed_at','received_at','sequence',
            'source_message_id','source','raw_value','raw_unit','canonical_value',
            'canonical_unit','quality','quality_reason','correlation_id','payload_hash','metadata',
        )
        value_groups=[]
        insert_parameters={}
        for index,item in enumerate(insert_items):
            names=[]
            for column in columns:
                key=f'{column}_{index}'
                names.append(f':{key}')
                insert_parameters[key]=item[column]
            value_groups.append(f"({', '.join(names[:-1])}, CAST(:metadata_{index} AS jsonb))")
        inserted=(await session.execute(text(f"""
            INSERT INTO twin_telemetry_samples({', '.join(columns)})
            VALUES {', '.join(value_groups)}
            ON CONFLICT (tenant_id,source_message_id)
              WHERE source_message_id IS NOT NULL DO NOTHING
            RETURNING id,source_message_id
        """),insert_parameters)).mappings().all()
        inserted_by_message={row['source_message_id']:row['id'] for row in inserted}

        concurrent=(await session.execute(text(f"""
            SELECT source_message_id,payload_hash
            FROM twin_telemetry_samples
            WHERE tenant_id=:t AND source_message_id IN ({', '.join(message_placeholders)})
        """),message_parameters)).mappings().all()
        concurrent_hashes={row['source_message_id']:row['payload_hash'] for row in concurrent}
        for message_id in unique_prepared:
            if concurrent_hashes.get(message_id)!=batch_hashes[message_id]:
                raise HTTPException(409,'TELEMETRY_MESSAGE_ID_CONFLICT')

    if inserted_by_message:
        latest_by_point={}
        inserted_items=[]
        for message_id,item in unique_prepared.items():
            if message_id not in inserted_by_message:
                continue
            item['sample_id']=inserted_by_message[message_id]
            inserted_items.append(item)
            current=latest_by_point.get(item['point_id'])
            if current is None or item['observed_at']>=current['observed_at']:
                latest_by_point[item['point_id']]=item

        state_values=[]
        state_parameters={}
        for index,item in enumerate(latest_by_point.values()):
            state_values.append(
                f"(:tenant_{index},:point_{index},:observed_{index},:received_{index},"
                f":value_{index},:unit_{index},:quality_{index},:reason_{index},:sample_{index})"
            )
            state_parameters.update({
                f'tenant_{index}':tenant,f'point_{index}':item['point_id'],
                f'observed_{index}':item['observed_at'],f'received_{index}':item['received_at'],
                f'value_{index}':item['canonical_value'],f'unit_{index}':item['canonical_unit'],
                f'quality_{index}':item['quality'],f'reason_{index}':item['quality_reason'],
                f'sample_{index}':item['sample_id'],
            })
        await session.execute(text(f"""
            INSERT INTO twin_point_states(
              tenant_id,point_id,observed_at,received_at,value,unit,quality,quality_reason,sample_id
            ) VALUES {', '.join(state_values)}
            ON CONFLICT(tenant_id,point_id) DO UPDATE SET
              observed_at=EXCLUDED.observed_at,received_at=EXCLUDED.received_at,
              value=EXCLUDED.value,unit=EXCLUDED.unit,quality=EXCLUDED.quality,
              quality_reason=EXCLUDED.quality_reason,sample_id=EXCLUDED.sample_id
            WHERE twin_point_states.observed_at<=EXCLUDED.observed_at
        """),state_parameters)

        device_ids=list(dict.fromkeys(
            item['device_id'] for item in inserted_items if item['device_id'] is not None
        ))
        if device_ids:
            device_parameters={'t':tenant,'r':now}
            device_placeholders=[]
            for index,device_id in enumerate(device_ids):
                key=f'device_{index}'
                device_parameters[key]=device_id
                device_placeholders.append(f':{key}')
            await session.execute(text(f"""
                UPDATE twin_devices SET last_seen_at=:r,updated_at=now(),status='ONLINE'
                WHERE tenant_id=:t AND id IN ({', '.join(device_placeholders)})
            """),device_parameters)

    sample_results=[]
    for item in prepared:
        message_id=item['source_message_id']
        is_first=original_indexes[message_id]==item['original_index']
        inserted=message_id in inserted_by_message
        status='accepted' if is_first and inserted else 'duplicate'
        sample_results.append({
            'source_message_id':message_id,'status':status,
            'quality':item['quality'],'quality_reason':item['quality_reason'],
            'canonical_value':item['canonical_value'],'canonical_unit':item['canonical_unit'],
            'observed_at':item['observed_at'],
        })
    return {
        'status':'accepted' if inserted_by_message else 'duplicate',
        'received':len(body.samples),'accepted':len(inserted_by_message),
        'duplicates':len(body.samples)-len(inserted_by_message),'samples':sample_results,
    }


@router.post('/devices',status_code=201)
async def create_device(body:DeviceIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    import json
    tenant=UUID(auth.tenant_id)
    if body.node_id:
        ok=await session.scalar(text('SELECT 1 FROM twin_nodes WHERE tenant_id=:t AND id=:id'),{'t':tenant,'id':body.node_id})
        if not ok: raise HTTPException(422,'node_id no pertenece al tenant')
    row=(await session.execute(text("""INSERT INTO twin_devices(tenant_id,node_id,external_device_id,device_type,manufacturer,model,serial_number,firmware_version,protocol,metadata)
        VALUES(:t,:n,:e,:dt,:m,:mo,:sn,:fw,:p,CAST(:md AS jsonb)) RETURNING id"""),{
        't':tenant,'n':body.node_id,'e':body.external_device_id,'dt':body.device_type,'m':body.manufacturer,'mo':body.model,
        'sn':body.serial_number,'fw':body.firmware_version,'p':body.protocol,'md':json.dumps(body.metadata)})).scalar_one()
    await session.commit()
    return {'id':str(row),'status':'created'}

@router.post('/points',status_code=201)
async def create_point(body:PointIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    import json
    tenant=UUID(auth.tenant_id)
    node_ok=await session.scalar(text('SELECT 1 FROM twin_nodes WHERE tenant_id=:t AND id=:id'),{'t':tenant,'id':body.node_id})
    if not node_ok: raise HTTPException(422,'node_id no pertenece al tenant')
    if body.device_id:
        dev_ok=await session.scalar(text('SELECT 1 FROM twin_devices WHERE tenant_id=:t AND id=:id'),{'t':tenant,'id':body.device_id})
        if not dev_ok: raise HTTPException(422,'device_id no pertenece al tenant')
    if body.engineering_min is not None and body.engineering_max is not None and body.engineering_max < body.engineering_min:
        raise HTTPException(422,'engineering_max debe ser >= engineering_min')
    try:
        row=(await session.execute(text("""INSERT INTO twin_points(tenant_id,node_id,device_id,code,name,semantic_kind,data_type,canonical_unit,engineering_min,engineering_max,stale_after_seconds,sampling_interval_seconds,metadata)
            VALUES(:t,:n,:d,:c,:name,:sk,:dt,:u,:mn,:mx,:st,:si,CAST(:md AS jsonb)) RETURNING id"""),{
            't':tenant,'n':body.node_id,'d':body.device_id,'c':body.code,'name':body.name,'sk':body.semantic_kind,'dt':body.data_type,
            'u':body.canonical_unit,'mn':body.engineering_min,'mx':body.engineering_max,'st':body.stale_after_seconds,'si':body.sampling_interval_seconds,'md':json.dumps(body.metadata)})).scalar_one()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(409,'point code already exists or violates a graph constraint') from exc
    await session.commit()
    return {'id':str(row),'status':'created'}

@router.post('/telemetry/samples',status_code=201)
async def ingest_operational_sample(body:TelemetrySampleIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    from datetime import timezone
    from backend.app.modules.digital_twin.domain.operational_telemetry import normalize_measurement, classify_quality
    tenant=UUID(auth.tenant_id)
    point=(await session.execute(text("""SELECT id,node_id,device_id,canonical_unit,engineering_min,engineering_max,stale_after_seconds
        FROM twin_points WHERE tenant_id=:t AND id=:p"""),{'t':tenant,'p':body.point_id})).mappings().first()
    if not point: raise HTTPException(404,'TWIN_POINT_NOT_FOUND')
    observed=body.observed_at if body.observed_at.tzinfo else body.observed_at.replace(tzinfo=timezone.utc)
    received=datetime.now(timezone.utc)
    try:
        normalized=normalize_measurement(body.value,body.unit,point['canonical_unit'])
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    quality,reason=classify_quality(observed_at=observed,received_at=received,source_quality=body.source_quality,value=normalized.canonical_value,
        engineering_min=point['engineering_min'],engineering_max=point['engineering_max'],stale_after_seconds=point['stale_after_seconds'])
    payload_hash=_telemetry_payload_hash(body,observed)
    try:
        row=(await session.execute(text("""INSERT INTO twin_telemetry_samples(tenant_id,point_id,device_id,observed_at,received_at,sequence,source_message_id,source,raw_value,raw_unit,canonical_value,canonical_unit,quality,quality_reason,correlation_id,payload_hash,metadata)
            VALUES(:t,:p,:d,:o,:r,:seq,:mid,:s,:rv,:ru,:cv,:cu,:q,:qr,:c,:ph,CAST(:md AS jsonb)) RETURNING id"""),{
            't':tenant,'p':body.point_id,'d':point['device_id'],'o':observed,'r':received,'seq':body.sequence,'mid':body.source_message_id,'s':body.source,
            'rv':body.value,'ru':body.unit,'cv':normalized.canonical_value,'cu':normalized.canonical_unit,'q':quality,'qr':reason,'c':body.correlation_id,'ph':payload_hash,'md':json.dumps(body.metadata)})).scalar_one()
    except IntegrityError as exc:
        logging.getLogger(__name__).info('twin sample rejected by an integrity constraint')
        await session.rollback()
        # set_config(...,true) es local a la transacción: tras rollback RLS vería 0 filas
        await session.execute(text("SELECT set_config('app.current_tenant_id', :tid, true)"),{'tid':str(tenant)})
        if body.source_message_id:
            existing=(await session.execute(text('SELECT id,quality,observed_at FROM twin_telemetry_samples WHERE tenant_id=:t AND source_message_id=:m'),{'t':tenant,'m':body.source_message_id})).mappings().first()
            if existing: return {'id':existing['id'],'status':'duplicate','quality':existing['quality'],'observed_at':existing['observed_at']}
        raise HTTPException(409,'TELEMETRY_SAMPLE_CONFLICT') from exc
    await session.execute(text("""INSERT INTO twin_point_states(tenant_id,point_id,observed_at,received_at,value,unit,quality,quality_reason,sample_id)
        VALUES(:t,:p,:o,:r,:v,:u,:q,:qr,:id)
        ON CONFLICT(tenant_id,point_id) DO UPDATE SET observed_at=EXCLUDED.observed_at,received_at=EXCLUDED.received_at,value=EXCLUDED.value,unit=EXCLUDED.unit,quality=EXCLUDED.quality,quality_reason=EXCLUDED.quality_reason,sample_id=EXCLUDED.sample_id
        WHERE twin_point_states.observed_at <= EXCLUDED.observed_at"""),{
        't':tenant,'p':body.point_id,'o':observed,'r':received,'v':normalized.canonical_value,'u':normalized.canonical_unit,'q':quality,'qr':reason,'id':row})
    await session.execute(text('UPDATE twin_devices SET last_seen_at=:r,updated_at=now(),status=\'ONLINE\' WHERE tenant_id=:t AND id=:d'),{'t':tenant,'d':point['device_id'],'r':received}) if point['device_id'] else None
    await session.commit()
    return {'id':row,'status':'accepted','quality':quality,'quality_reason':reason,'canonical_value':normalized.canonical_value,'canonical_unit':normalized.canonical_unit}


@router.post('/telemetry/samples/batch',status_code=202)
async def ingest_operational_batch(
    body:TelemetryBatchIn,
    auth:AuthContext=Depends(get_auth_context),
    session:AsyncSession=Depends(get_tenant_session),
):
    return await _ingest_operational_batch(body,auth,session)


@router.get('/simulations/catalog')
async def simulated_sensor_catalog(auth:AuthContext=Depends(get_auth_context)):
    return profile_catalog()


@router.get('/simulations/devices')
async def list_simulated_devices(auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    rows=(await session.execute(text("""
        SELECT d.id AS device_id,d.node_id,n.name AS node_name,d.metadata AS device_metadata,
               p.id AS point_id,p.code,p.name,p.semantic_kind,p.canonical_unit,
               s.value AS latest_value,s.unit AS latest_unit,s.quality AS latest_quality,
               s.observed_at AS latest_observed_at
        FROM twin_devices d
        JOIN twin_nodes n ON n.tenant_id=d.tenant_id AND n.id=d.node_id
        JOIN twin_points p ON p.tenant_id=d.tenant_id AND p.device_id=d.id
        LEFT JOIN twin_point_states s ON s.tenant_id=p.tenant_id AND s.point_id=p.id
        WHERE d.tenant_id=:t AND d.metadata->>'data_origin'='simulated'
        ORDER BY d.created_at DESC,d.id
    """),{'t':UUID(auth.tenant_id)})).mappings().all()
    return [{
        'device_id':str(row['device_id']),'node_id':str(row['node_id']),
        'node_name':row['node_name'],'point_id':str(row['point_id']),
        'code':row['code'],'name':row['name'],'semantic_kind':row['semantic_kind'],
        'unit':row['canonical_unit'],'profile_id':row['device_metadata']['profile_id'],
        'latest_value':row['latest_value'],'latest_unit':row['latest_unit'],
        'latest_quality':row['latest_quality'],'latest_observed_at':row['latest_observed_at'],
        'data_origin':'simulated','hardware_connected':False,
    } for row in rows]


@router.post('/simulations/devices',status_code=201)
async def create_simulated_device(body:SimulatedDeviceIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    import json
    tenant=UUID(auth.tenant_id)
    try:
        profile=get_profile(body.profile_id)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    node_exists=await session.scalar(
        text('SELECT 1 FROM twin_nodes WHERE tenant_id=:t AND id=:n'),
        {'t':tenant,'n':body.node_id},
    )
    if not node_exists:
        raise HTTPException(404,'TWIN_NODE_NOT_FOUND')

    device_id=uuid4()
    metadata={
        'data_origin':'simulated','profile_id':profile.profile_id,'simulation_version':1,
        'hardware_connected':False,
        'safety_boundary':'synthetic telemetry only; no physical commands',
    }
    try:
        await session.execute(text("""
            INSERT INTO twin_devices(
              id,tenant_id,node_id,external_device_id,device_type,protocol,metadata
            ) VALUES(:id,:t,:n,:external_id,'virtual_sensor','SIMULATED',CAST(:metadata AS jsonb))
        """),{
            'id':device_id,'t':tenant,'n':body.node_id,
            'external_id':f'virtual:{device_id}','metadata':json.dumps(metadata),
        })
        point_id=(await session.execute(text("""
            INSERT INTO twin_points(
              tenant_id,node_id,device_id,code,name,semantic_kind,data_type,canonical_unit,
              engineering_min,engineering_max,stale_after_seconds,sampling_interval_seconds,metadata
            ) VALUES(:t,:n,:d,:code,:name,:kind,'float64',:unit,:minimum,:maximum,300,30,CAST(:metadata AS jsonb))
            RETURNING id
        """),{
            't':tenant,'n':body.node_id,'d':device_id,'code':body.code,
            'name':body.name or profile.name,'kind':profile.semantic_kind,'unit':profile.unit,
            'minimum':profile.engineering_min,'maximum':profile.engineering_max,
            'metadata':json.dumps({'data_origin':'simulated','profile_id':profile.profile_id}),
        })).scalar_one()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409,'SIMULATED_DEVICE_CODE_ALREADY_EXISTS') from exc
    await session.commit()
    return {
        'device_id':str(device_id),'point_id':str(point_id),'node_id':str(body.node_id),
        'code':body.code,'name':body.name or profile.name,'profile_id':profile.profile_id,
        'data_origin':'simulated','hardware_connected':False,
    }


@router.post('/simulations/devices/{device_id}/run',status_code=201)
async def run_sensor_simulation(
    device_id:UUID,
    body:SimulationRunIn,
    auth:AuthContext=Depends(get_auth_context),
    session:AsyncSession=Depends(get_tenant_session),
):
    tenant=UUID(auth.tenant_id)
    device=(await session.execute(text("""
        SELECT d.node_id,d.metadata,p.id AS point_id
        FROM twin_devices d
        JOIN twin_points p ON p.tenant_id=d.tenant_id AND p.device_id=d.id
        WHERE d.tenant_id=:t AND d.id=:d AND d.metadata->>'data_origin'='simulated'
        ORDER BY p.created_at,p.id LIMIT 1
    """),{'t':tenant,'d':device_id})).mappings().first()
    if not device:
        raise HTTPException(404,'SIMULATED_DEVICE_NOT_FOUND')
    try:
        profile=get_profile(device['metadata']['profile_id'])
        values=generate_readings(profile,scenario=body.scenario,run_id=body.run_id)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc

    now=datetime.now(timezone.utc)
    first_sequence=int(now.timestamp()*1000)
    samples=TelemetryBatchIn(samples=[
        TelemetrySampleIn(
            point_id=device['point_id'],
            value=value,
            unit=profile.unit,
            observed_at=now-timedelta(seconds=(len(values)-index-1)*30),
            source='virtual-sensor-simulator',
            source_message_id=f"sim:{device_id}:{body.run_id}:{index}",
            sequence=first_sequence+index,
            source_quality='GOOD',
            correlation_id=str(body.run_id),
            metadata={
                'data_origin':'simulated','profile_id':profile.profile_id,
                'scenario':body.scenario,'simulation_run_id':str(body.run_id),
                'sample_index':index+1,'hardware_connected':False,
            },
        )
        for index,value in enumerate(values)
    ])
    ingestion=await _ingest_operational_batch(samples,auth,session)
    if ingestion['accepted']==0:
        return {
            'run_id':str(body.run_id),'status':'duplicate','scenario':body.scenario,
            'data_origin':'simulated','hardware_connected':False,'samples':[],
            'diagnostic':None,
        }
    diagnostic=await evaluate_diagnostics(
        DiagnosticEvaluateIn(node_id=device['node_id'],window_minutes=60,min_samples=3),
        auth,
        session,
    )
    return {
        'run_id':str(body.run_id),'status':'accepted','scenario':body.scenario,
        'data_origin':'simulated','hardware_connected':False,'samples':ingestion['samples'],
        'diagnostic':diagnostic,
    }


class DiagnosticEvaluateIn(BaseModel):
    node_id: UUID
    window_minutes: int = Field(default=60, ge=5, le=10080)
    min_samples: int = Field(default=3, ge=2, le=1000)


@router.post('/diagnostics/evaluate', status_code=201)
async def evaluate_diagnostics(
    body: DiagnosticEvaluateIn,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Run an auditable deterministic engineering diagnostic over operational telemetry.

    This endpoint augments the existing operational_anomalies/autonomous plane;
    it does not create a parallel anomaly lifecycle.
    """
    import json
    from datetime import timedelta, timezone
    from uuid import uuid4
    from backend.app.modules.digital_twin.domain.diagnostic_engine import diagnose_point, evaluate, classify_severity

    tenant = UUID(auth.tenant_id)
    node = (await session.execute(text(
        'SELECT id FROM twin_nodes WHERE tenant_id=:t AND id=:n'
    ), {'t': tenant, 'n': body.node_id})).scalar()
    if not node:
        raise HTTPException(404, 'TWIN_NODE_NOT_FOUND')

    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=body.window_minutes)
    points = (await session.execute(text("""
        SELECT id, semantic_kind, engineering_min, engineering_max, canonical_unit
        FROM twin_points
        WHERE tenant_id=:t AND node_id=:n
        ORDER BY code
    """), {'t': tenant, 'n': body.node_id})).mappings().all()
    if not points:
        raise HTTPException(422, 'TWIN_NODE_HAS_NO_OPERATIONAL_POINTS')

    features = []
    evidence = {'window_started_at': start.isoformat(), 'window_ended_at': end.isoformat(), 'points': []}
    for point in points:
        rows = (await session.execute(text("""
            SELECT canonical_value, quality
            FROM twin_telemetry_samples
            WHERE tenant_id=:t AND point_id=:p
              AND observed_at >= :start AND observed_at <= :end
            ORDER BY observed_at ASC
            LIMIT 1000
        """), {'t': tenant, 'p': point['id'], 'start': start, 'end': end})).mappings().all()
        if len(rows) < body.min_samples:
            continue
        f = diagnose_point(
            point_id=str(point['id']),
            semantic_kind=point['semantic_kind'],
            values=[float(r['canonical_value']) for r in rows],
            qualities=[r['quality'] for r in rows],
            engineering_min=point['engineering_min'],
            engineering_max=point['engineering_max'],
        )
        features.append(f)
        evidence['points'].append({'point_id': str(point['id']), 'sample_count': len(rows), 'semantic_kind': point['semantic_kind']})

    if not features:
        raise HTTPException(422, 'INSUFFICIENT_TELEMETRY_FOR_DIAGNOSIS')

    result = evaluate(features)
    run_id = uuid4()
    await session.execute(text("""
        INSERT INTO twin_diagnostic_runs(
          diagnostic_run_id,tenant_id,node_id,window_started_at,window_ended_at,
          method,health_score,severity,confidence,feature_count,probable_causes,evidence)
        VALUES(:id,:t,:n,:ws,:we,'deterministic_engineering_v1',:h,:s,:c,:fc,CAST(:pc AS jsonb),CAST(:ev AS jsonb))
    """), {
        'id': run_id, 't': tenant, 'n': body.node_id, 'ws': start, 'we': end,
        'h': result.health_score, 's': result.severity, 'c': result.confidence,
        'fc': len(result.features), 'pc': json.dumps(list(result.probable_causes)), 'ev': json.dumps(evidence),
    })

    for f in result.features:
        await session.execute(text("""
            INSERT INTO twin_diagnostic_features(
              tenant_id,diagnostic_run_id,point_id,latest_value,baseline_value,scale,
              deviation_score,trend_score,persistence_score,quality_penalty,impairment_score,evidence)
            VALUES(:t,:r,:p,:lv,:bv,:sc,:d,:tr,:pe,:qp,:im,CAST(:ev AS jsonb))
        """), {
            't': tenant, 'r': run_id, 'p': UUID(f.point_id), 'lv': f.latest,
            'bv': f.baseline, 'sc': f.scale, 'd': f.deviation, 'tr': f.trend,
            'pe': f.persistence, 'qp': f.quality_penalty, 'im': f.impairment,
            'ev': json.dumps({'semantic_kind': f.semantic_kind}),
        })
        if f.impairment >= 0.50:
            anomaly_id = uuid4()
            correlation = f'twin-diagnostic:{run_id}:{f.point_id}'
            severity = classify_severity(f.impairment)
            causes = [c for c in result.probable_causes if f.semantic_kind.lower() in {str(x).lower() for x in c.get('basis', [])} or f.point_id in c.get('basis', [])]
            await session.execute(text("""
                INSERT INTO operational_anomalies(
                  anomaly_id,tenant_id,node_id,metric,observed_value,baseline_value,score,severity,
                  detection_method,evidence,correlation_id,twin_point_id,diagnostic_run_id,
                  diagnostic_confidence,health_impact,probable_causes)
                VALUES(:id,:t,:n,:m,:v,:b,:sc,:sev,'twin_deterministic_diagnostic',CAST(:ev AS jsonb),
                       :corr,:p,:run,:conf,:impact,CAST(:causes AS jsonb))
                ON CONFLICT(tenant_id,correlation_id) DO UPDATE SET
                  score=EXCLUDED.score,severity=EXCLUDED.severity,evidence=EXCLUDED.evidence,
                  diagnostic_confidence=EXCLUDED.diagnostic_confidence,health_impact=EXCLUDED.health_impact,
                  probable_causes=EXCLUDED.probable_causes,diagnostic_run_id=EXCLUDED.diagnostic_run_id
            """), {
                'id': anomaly_id, 't': tenant, 'n': body.node_id, 'm': f.semantic_kind,
                'v': f.latest, 'b': f.baseline, 'sc': f.impairment, 'sev': severity,
                'ev': json.dumps({'deviation': f.deviation, 'trend': f.trend, 'persistence': f.persistence, 'quality_penalty': f.quality_penalty}),
                'corr': correlation, 'p': UUID(f.point_id), 'run': run_id,
                'conf': result.confidence, 'impact': f.impairment, 'causes': json.dumps(causes),
            })
            from backend.app.platform.realtime.service import publish
            await publish(session, tenant_id=tenant, topic='twin.anomaly.detected', payload={'anomaly_id': str(anomaly_id), 'node_id': str(body.node_id), 'severity': severity, 'run_id': str(run_id)}, correlation_id=correlation)

    await session.execute(text("""
        INSERT INTO twin_health_assessments(tenant_id,node_id,assessed_at,health_score,severity,confidence,diagnostic_run_id)
        VALUES(:t,:n,:at,:h,:s,:c,:r)
        ON CONFLICT(tenant_id,node_id) DO UPDATE SET assessed_at=EXCLUDED.assessed_at,
          health_score=EXCLUDED.health_score,severity=EXCLUDED.severity,confidence=EXCLUDED.confidence,
          diagnostic_run_id=EXCLUDED.diagnostic_run_id
    """), {'t': tenant, 'n': body.node_id, 'at': end, 'h': result.health_score, 's': result.severity, 'c': result.confidence, 'r': run_id})
    await session.execute(text("""
        INSERT INTO twin_state_snapshots(tenant_id,node_id,captured_at,state,state_data,health_score,confidence,derived_from)
        VALUES(:t,:n,:at,:state,CAST(:sd AS jsonb),:h,:c,CAST(:df AS jsonb))
    """), {
        't': tenant, 'n': body.node_id, 'at': end,
        'state': result.severity.upper(),
        'sd': json.dumps({'diagnostic_run_id': str(run_id), 'method': 'deterministic_engineering_v1'}),
        'h': result.health_score, 'c': result.confidence,
        'df': json.dumps([{'diagnostic_run_id': str(run_id), 'type': 'diagnostic'}]),
    })
    await session.commit()
    return {
        'diagnostic_run_id': str(run_id), 'node_id': str(body.node_id),
        'health_score': result.health_score, 'severity': result.severity,
        'confidence': result.confidence, 'feature_count': len(result.features),
        'probable_causes': list(result.probable_causes),
        'anomalies_created_or_updated': sum(1 for f in result.features if f.impairment >= 0.50),
        'method': 'deterministic_engineering_v1',
    }

@router.get('/points/{point_id}/latest')
async def latest_point(point_id:UUID,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    row=(await session.execute(text("""SELECT p.id,p.code,p.name,p.semantic_kind,p.canonical_unit,s.observed_at,s.received_at,s.value,s.unit,s.quality,s.quality_reason,s.sample_id
        FROM twin_points p LEFT JOIN twin_point_states s ON s.tenant_id=p.tenant_id AND s.point_id=p.id
        WHERE p.tenant_id=:t AND p.id=:p"""),{'t':UUID(auth.tenant_id),'p':point_id})).mappings().first()
    if not row: raise HTTPException(404,'TWIN_POINT_NOT_FOUND')
    return dict(row)

class DiagnosticEnrichIn(BaseModel):
    max_lag: int = Field(default=2, ge=0, le=10)


@router.post('/diagnostics/{run_id}/enrich')
async def enrich_diagnostic_run(
    run_id: UUID,
    body: DiagnosticEnrichIn,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Add explainable change-point/hypothesis evidence to an existing diagnostic run.

    This is additive: it reuses the run and operational anomaly lifecycle already
    created by Phase 3; it never fabricates root-cause certainty.
    """
    import json
    from uuid import uuid4
    from backend.app.modules.digital_twin.domain.advanced_diagnostics import normalized_change_point, build_hypotheses

    tenant = UUID(auth.tenant_id)
    run = (await session.execute(text("""
        SELECT diagnostic_run_id,node_id,window_started_at,window_ended_at
        FROM twin_diagnostic_runs WHERE tenant_id=:t AND diagnostic_run_id=:r
    """), {'t': tenant, 'r': run_id})).mappings().first()
    if not run:
        raise HTTPException(404, 'DIAGNOSTIC_RUN_NOT_FOUND')

    rows = (await session.execute(text("""
        SELECT f.point_id,f.impairment_score,f.quality_penalty,p.semantic_kind,p.engineering_min,p.engineering_max
        FROM twin_diagnostic_features f
        JOIN twin_points p ON p.tenant_id=f.tenant_id AND p.id=f.point_id
        WHERE f.tenant_id=:t AND f.diagnostic_run_id=:r
    """), {'t': tenant, 'r': run_id})).mappings().all()
    if not rows:
        raise HTTPException(422, 'DIAGNOSTIC_RUN_HAS_NO_FEATURES')

    feature_dicts = [dict(r) for r in rows]
    cps = []
    for f in rows:
        samples = (await session.execute(text("""
            SELECT canonical_value FROM twin_telemetry_samples
            WHERE tenant_id=:t AND point_id=:p AND observed_at BETWEEN :s AND :e
            ORDER BY observed_at ASC LIMIT 1000
        """), {'t': tenant, 'p': f['point_id'], 's': run['window_started_at'], 'e': run['window_ended_at']})).scalars().all()
        if len(samples) < 4:
            continue
        scale = max(float(f['engineering_max'] - f['engineering_min']) * .05 if f['engineering_min'] is not None and f['engineering_max'] is not None else 0.0, 1e-9)
        cp = normalized_change_point(samples, scale)
        cps.append((f, cp))
        await session.execute(text("""
            INSERT INTO twin_diagnostic_change_points(tenant_id,diagnostic_run_id,point_id,detected,magnitude,before_value,after_value,direction,evidence)
            VALUES(:t,:r,:p,:d,:m,:b,:a,:dir,CAST(:ev AS jsonb))
        """), {'t':tenant,'r':run_id,'p':f['point_id'],'d':cp.detected,'m':cp.magnitude,'b':cp.before,'a':cp.after,'dir':cp.direction,'ev':json.dumps(cp.evidence)})
        for fd in feature_dicts:
            if fd['point_id'] == f['point_id']:
                fd['change_point_magnitude'] = cp.magnitude
                break

    hypotheses = build_hypotheses(feature_dicts)
    for h in hypotheses:
        await session.execute(text("""
            INSERT INTO twin_diagnostic_hypotheses(tenant_id,diagnostic_run_id,code,confidence,severity,evidence,recommended_actions)
            VALUES(:t,:r,:c,:cf,:s,CAST(:e AS jsonb),CAST(:a AS jsonb))
        """), {'t':tenant,'r':run_id,'c':h.code,'cf':h.confidence,'s':h.severity,'e':json.dumps(list(h.evidence)),'a':json.dumps(list(h.recommended_actions))})

    anomalies = (await session.execute(text("""
        SELECT anomaly_id FROM operational_anomalies WHERE tenant_id=:t AND diagnostic_run_id=:r
    """), {'t':tenant,'r':run_id})).scalars().all()
    for anomaly_id in anomalies:
        top = hypotheses[0] if hypotheses else None
        if not top:
            continue
        existing = (await session.execute(text("""
            SELECT diagnosis_id FROM operational_diagnoses
            WHERE tenant_id=:t AND anomaly_id=:a AND diagnosis_code=:c AND status='proposed'
            ORDER BY created_at DESC LIMIT 1
        """), {'t':tenant,'a':anomaly_id,'c':top.code})).scalar()
        if not existing:
            await session.execute(text("""
                INSERT INTO operational_diagnoses(tenant_id,anomaly_id,agent,diagnosis_code,confidence,root_cause,evidence,recommended_actions,status)
                VALUES(:t,:a,'digital-twin-engineering-v2',:c,:cf,CAST(:rc AS jsonb),CAST(:ev AS jsonb),CAST(:ra AS jsonb),'proposed')
            """), {'t':tenant,'a':anomaly_id,'c':top.code,'cf':top.confidence,
                   'rc':json.dumps({'hypothesis':top.code,'certainty':'probable','not_root_cause_proof':True}),
                   'ev':json.dumps({'diagnostic_run_id':str(run_id),'evidence_points':list(top.evidence),'change_points':sum(1 for _,cp in cps if cp.detected)}),
                   'ra':json.dumps(list(top.recommended_actions))})

    await session.commit()
    return {'diagnostic_run_id':str(run_id),'change_points':sum(1 for _,cp in cps if cp.detected),'points_analyzed':len(cps),'hypotheses':[h.__dict__ for h in hypotheses],'operational_diagnoses_linked':len(anomalies) if hypotheses else 0}


@router.get('/diagnostics/{run_id}/explain')
async def explain_diagnostic_run(
    run_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Return the auditable evidence chain for a diagnostic run."""
    tenant = UUID(auth.tenant_id)
    run = (await session.execute(text("SELECT * FROM twin_diagnostic_runs WHERE tenant_id=:t AND diagnostic_run_id=:r"), {'t':tenant,'r':run_id})).mappings().first()
    if not run:
        raise HTTPException(404,'DIAGNOSTIC_RUN_NOT_FOUND')
    features=(await session.execute(text("SELECT * FROM twin_diagnostic_features WHERE tenant_id=:t AND diagnostic_run_id=:r ORDER BY impairment_score DESC"),{'t':tenant,'r':run_id})).mappings().all()
    hypotheses=(await session.execute(text("SELECT * FROM twin_diagnostic_hypotheses WHERE tenant_id=:t AND diagnostic_run_id=:r ORDER BY confidence DESC"),{'t':tenant,'r':run_id})).mappings().all()
    changes=(await session.execute(text("SELECT * FROM twin_diagnostic_change_points WHERE tenant_id=:t AND diagnostic_run_id=:r ORDER BY magnitude DESC"),{'t':tenant,'r':run_id})).mappings().all()
    anomalies=(await session.execute(text("SELECT anomaly_id,metric,severity,status,diagnostic_confidence,probable_causes FROM operational_anomalies WHERE tenant_id=:t AND diagnostic_run_id=:r"),{'t':tenant,'r':run_id})).mappings().all()
    return {'run':dict(run),'features':[dict(x) for x in features],'hypotheses':[dict(x) for x in hypotheses],'change_points':[dict(x) for x in changes],'anomalies':[dict(x) for x in anomalies]}

# --- Phase 3 continuation: system-level diagnosis and dependency propagation ---
class DependencyEdgeIn(BaseModel):
    source_node_id: UUID
    target_node_id: UUID
    relation: str = Field(min_length=1, max_length=80)
    criticality: float = Field(default=1.0, ge=0, le=1)
    propagation_factor: float = Field(default=1.0, ge=0, le=1)
    direction: str = Field(default='source_to_target', max_length=24)
    provenance_id: UUID | None = None
    metadata: dict = Field(default_factory=dict)

class SystemDiagnosticIn(BaseModel):
    system_node_id: UUID
    source_run_id: UUID | None = None
    max_depth: int = Field(default=8, ge=1, le=32)
    min_impact: float = Field(default=0.10, ge=0, le=1)


@router.post('/dependencies', status_code=201)
async def create_dependency_edge(
    body: DependencyEdgeIn,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    import json
    tenant = UUID(auth.tenant_id)
    if body.source_node_id == body.target_node_id:
        raise HTTPException(422, 'DEPENDENCY_SELF_REFERENCE')
    rows = (await session.execute(text(
        "SELECT id FROM twin_nodes WHERE tenant_id=:t AND id IN (:s,:d)"
    ), {'t': tenant, 's': body.source_node_id, 'd': body.target_node_id})).all()
    if len(rows) != 2:
        raise HTTPException(422, 'DEPENDENCY_NODE_NOT_IN_TENANT')
    try:
        dep_id = (await session.execute(text("""
            INSERT INTO twin_dependency_edges(
                tenant_id,source_node_id,target_node_id,relation,criticality,
                propagation_factor,direction,provenance_id,metadata)
            VALUES(:t,:s,:d,:r,:c,:p,:dir,:prov,CAST(:m AS jsonb))
            RETURNING dependency_id
        """), {
            't': tenant, 's': body.source_node_id, 'd': body.target_node_id,
            'r': body.relation, 'c': body.criticality, 'p': body.propagation_factor,
            'dir': body.direction, 'prov': body.provenance_id, 'm': json.dumps(body.metadata)
        })).scalar_one()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(409, 'DEPENDENCY_EDGE_ALREADY_EXISTS_OR_INVALID') from exc
    await session.commit()
    return {'dependency_id': str(dep_id), 'status': 'created'}


@router.post('/diagnostics/system', status_code=201)
async def evaluate_system_diagnostic(
    body: SystemDiagnosticIn,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Aggregate node health and propagate active diagnostic impact through dependencies.

    This is deterministic systems engineering, not a claim of automated root-cause proof.
    """
    import json
    from uuid import uuid4
    from backend.app.modules.digital_twin.domain.system_diagnostics import aggregate_health, propagate_impact
    tenant = UUID(auth.tenant_id)
    exists = await session.scalar(text(
        'SELECT 1 FROM twin_nodes WHERE tenant_id=:t AND id=:n'
    ), {'t': tenant, 'n': body.system_node_id})
    if not exists:
        raise HTTPException(404, 'SYSTEM_NODE_NOT_FOUND')

    descendants = (await session.execute(text("""
        WITH RECURSIVE tree AS (
            SELECT id FROM twin_nodes WHERE tenant_id=:t AND id=:root
            UNION ALL
            SELECT n.id FROM twin_nodes n JOIN tree p ON n.parent_id=p.id WHERE n.tenant_id=:t
        )
        SELECT id FROM tree
    """), {'t': tenant, 'root': body.system_node_id})).scalars().all()
    if not descendants:
        raise HTTPException(422, 'SYSTEM_HAS_NO_NODES')

    health_rows = (await session.execute(text("""
        SELECT DISTINCT ON (node_id) node_id, health_score, confidence
        FROM twin_health_assessments
        WHERE tenant_id=:t AND node_id = ANY(:nodes)
        ORDER BY node_id, assessed_at DESC
    """), {'t': tenant, 'nodes': descendants})).mappings().all()
    if not health_rows:
        raise HTTPException(422, 'SYSTEM_HAS_NO_HEALTH_ASSESSMENTS')
    health = {str(r['node_id']): float(r['health_score']) for r in health_rows}
    weights = {str(r['node_id']): 1.0 for r in health_rows}
    confidence = {str(r['node_id']): float(r['confidence']) for r in health_rows}

    relations = (await session.execute(text("""
        SELECT source_node_id AS source, target_node_id AS target, relation, criticality, propagation_factor
        FROM twin_dependency_edges
        WHERE tenant_id=:t AND active=true
          AND source_node_id = ANY(:nodes) AND target_node_id = ANY(:nodes)
    """), {'t': tenant, 'nodes': descendants})).mappings().all()

    anomaly_rows = (await session.execute(text("""
        SELECT DISTINCT ON (node_id) anomaly_id, node_id, score, severity, metric, evidence
        FROM operational_anomalies
        WHERE tenant_id=:t AND node_id = ANY(:nodes)
        ORDER BY node_id, detected_at DESC
    """), {'t': tenant, 'nodes': descendants})).mappings().all()

    all_paths = []
    for anomaly in anomaly_rows:
        impact = min(1.0, max(0.0, float(anomaly['score'] or 0.0)))
        paths = propagate_impact(str(anomaly['node_id']), relations, impact, body.max_depth, body.min_impact)
        all_paths.extend(paths)
    assessment = aggregate_health(health, weights, confidence)
    impacted = sorted({p.target for p in all_paths})
    critical_paths = [p.__dict__ for p in sorted(all_paths, key=lambda p: p.impact, reverse=True)[:32]]
    evidence = {
        'node_count': len(health_rows),
        'dependency_edge_count': len(relations),
        'anomaly_count': len(anomaly_rows),
        'propagation_model': 'deterministic_weighted_dependency_v1',
        'root_cause_claim': False,
    }
    aid = uuid4()
    await session.execute(text("""
        INSERT INTO twin_system_assessments(
            assessment_id,tenant_id,system_node_id,health_score,severity,confidence,
            source_run_id,impacted_nodes,critical_paths,evidence)
        VALUES(:id,:t,:n,:h,:s,:c,:r,CAST(:i AS jsonb),CAST(:p AS jsonb),CAST(:e AS jsonb))
    """), {
        'id': aid, 't': tenant, 'n': body.system_node_id, 'h': assessment.health_score,
        's': assessment.severity, 'c': assessment.confidence, 'r': body.source_run_id,
        'i': json.dumps(impacted), 'p': json.dumps(critical_paths), 'e': json.dumps(evidence)
    })
    await session.commit()
    return {
        'assessment_id': str(aid), 'system_node_id': str(body.system_node_id),
        'health_score': assessment.health_score, 'severity': assessment.severity,
        'confidence': assessment.confidence, 'impacted_nodes': impacted,
        'critical_paths': critical_paths, 'evidence': evidence,
    }


@router.get('/diagnostics/system/{assessment_id}/explain')
async def explain_system_diagnostic(
    assessment_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    row = (await session.execute(text("""
        SELECT assessment_id,system_node_id,assessed_at,health_score,severity,confidence,
               source_run_id,impacted_nodes,critical_paths,evidence
        FROM twin_system_assessments
        WHERE tenant_id=:t AND assessment_id=:a
    """), {'t': UUID(auth.tenant_id), 'a': assessment_id})).mappings().first()
    if not row:
        raise HTTPException(404, 'SYSTEM_ASSESSMENT_NOT_FOUND')
    return dict(row)

# --- Phase 3 continuation: temporal failure-chain evidence ---
class FailureChainIn(BaseModel):
    diagnostic_run_id: UUID
    max_gap_minutes: int = Field(default=60, ge=1, le=10080)


class MaintenanceWorkRequestIn(BaseModel):
    asset_id: UUID | None = None
    maintenance_type: str = Field(default='CONDITION_BASED', min_length=1, max_length=80)
    estimated_cost: float = Field(default=0, ge=0)
    severity: str = Field(default='high', pattern='^(info|low|medium|high|critical)$')
    approval_required: bool = True
    requested_by_agent: str = Field(default='digital-twin-engineering-v3', min_length=1, max_length=160)


@router.post('/diagnostics/{run_id}/maintenance-work-request', status_code=201)
async def create_maintenance_work_request(
    run_id: UUID,
    body: MaintenanceWorkRequestIn,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Create a governed maintenance request from an evaluated failure chain.

    This does not silently create a maintenance order. It persists a durable work
    request and emits an outbox contract for the .NET maintenance core.
    """
    import json
    from uuid import uuid4
    tenant = UUID(auth.tenant_id)
    chain = (await session.execute(text("SELECT * FROM twin_failure_chains WHERE tenant_id=:t AND diagnostic_run_id=:r"), {'t':tenant,'r':run_id})).mappings().first()
    if not chain:
        raise HTTPException(404, 'FAILURE_CHAIN_NOT_FOUND')
    anomalies = (await session.execute(text("""
        SELECT anomaly_id,node_id,severity,metric,score,evidence
        FROM operational_anomalies
        WHERE tenant_id=:t AND diagnostic_run_id=:r
        ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END, detected_at ASC
        LIMIT 20
    """), {'t':tenant,'r':run_id})).mappings().all()
    if not anomalies:
        raise HTTPException(422, 'NO_OPERATIONAL_ANOMALIES_FOR_RUN')
    asset_id = body.asset_id
    if asset_id is None:
        # Resolve an explicit asset binding only; never guess from a twin node id.
        for anomaly in anomalies:
            binding = (await session.execute(text("""
                SELECT identifier FROM twin_bindings
                WHERE tenant_id=:t AND node_id=:n
                  AND lower(identifier_type) IN ('asset_id','asset')
                ORDER BY confidence DESC, created_at DESC LIMIT 1
            """), {'t':tenant,'n':anomaly['node_id']})).scalar()
            if binding:
                try:
                    asset_id = UUID(str(binding)); break
                except ValueError:
                    continue
    if asset_id is None:
        raise HTTPException(422, 'ASSET_BINDING_REQUIRED')
    # Validate that the selected asset is represented in the twin binding graph.
    bound = await session.scalar(text("SELECT 1 FROM twin_bindings WHERE tenant_id=:t AND identifier=:i AND lower(identifier_type) IN ('asset_id','asset') LIMIT 1"), {'t':tenant,'i':str(asset_id)})
    if not bound:
        raise HTTPException(422, 'ASSET_NOT_BOUND_TO_TWIN')
    request_id = uuid4()
    top_severity = body.severity
    if any(a['severity'] == 'critical' for a in anomalies): top_severity = 'critical'
    elif any(a['severity'] == 'high' for a in anomalies) and top_severity in ('info','low','medium'): top_severity = 'high'
    payload = {
        'work_request_id': str(request_id), 'tenant_id': str(tenant), 'asset_id': str(asset_id),
        'diagnostic_run_id': str(run_id), 'failure_chain_id': str(chain['chain_id']),
        'maintenance_type': body.maintenance_type, 'estimated_cost': body.estimated_cost,
        'severity': top_severity, 'approval_required': body.approval_required,
        'requested_by_agent': body.requested_by_agent,
        'chain_confidence': float(chain['chain_confidence']),
        'claim_level': chain['claim_level'],
        'anomaly_ids': [str(a['anomaly_id']) for a in anomalies],
        'rationale': 'Condition-based maintenance request derived from temporal/dependency evidence; root cause not automatically proven.'
    }
    await session.execute(text("""
        INSERT INTO twin_maintenance_work_requests(request_id,tenant_id,diagnostic_run_id,failure_chain_id,asset_id,severity,maintenance_type,estimated_cost,approval_required,payload)
        VALUES(:id,:t,:r,:c,:a,:s,:m,:cost,:approval,CAST(:p AS jsonb))
        ON CONFLICT(tenant_id,diagnostic_run_id,asset_id) DO UPDATE SET severity=EXCLUDED.severity,maintenance_type=EXCLUDED.maintenance_type,estimated_cost=EXCLUDED.estimated_cost,approval_required=EXCLUDED.approval_required,payload=EXCLUDED.payload
        RETURNING request_id
    """), {'id':request_id,'t':tenant,'r':run_id,'c':chain['chain_id'],'a':asset_id,'s':top_severity,'m':body.maintenance_type,'cost':body.estimated_cost,'approval':body.approval_required,'p':json.dumps(payload)})
    stored = await session.scalar(text('SELECT request_id FROM twin_maintenance_work_requests WHERE tenant_id=:t AND diagnostic_run_id=:r AND asset_id=:a'), {'t':tenant,'r':run_id,'a':asset_id})
    existing_event = await session.scalar(text("""SELECT id FROM outbox_events
        WHERE tenant_id=:t AND event_type='maintenance.work-request.proposed'
          AND aggregate_type='twin_maintenance_work_request' AND aggregate_id=:a
        ORDER BY created_at DESC LIMIT 1"""), {'t': tenant, 'a': str(stored)})
    event_id = existing_event or await enqueue(session, tenant, 'maintenance.work-request.proposed', 'twin_maintenance_work_request', stored, payload, producer='digital-twin')
    await session.commit()
    return {'work_request_id':str(stored),'outbox_event_id':str(event_id),'status':'PROPOSED','approval_required':body.approval_required,'maintenance_core_contract':'POST /api/maintenance/orders/from-digital-twin'}


@router.post('/diagnostics/{run_id}/failure-chain', status_code=201)
async def build_failure_chain_endpoint(
    run_id: UUID,
    body: FailureChainIn,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    """Rank temporal/dependency evidence around anomalies linked to a diagnostic run.

    This endpoint explicitly returns correlation evidence; it never labels a root cause as proven.
    """
    import json
    from uuid import uuid4
    from backend.app.modules.digital_twin.domain.failure_chain import build_failure_chain, to_dict
    tenant = UUID(auth.tenant_id)
    if body.diagnostic_run_id != run_id:
        raise HTTPException(422, 'RUN_ID_MISMATCH')
    exists = await session.scalar(text(
        'SELECT 1 FROM twin_diagnostic_runs WHERE tenant_id=:t AND diagnostic_run_id=:r'
    ), {'t': tenant, 'r': run_id})
    if not exists:
        raise HTTPException(404, 'DIAGNOSTIC_RUN_NOT_FOUND')
    anomalies = (await session.execute(text("""
        SELECT anomaly_id,node_id,metric,score,severity,detected_at,evidence
        FROM operational_anomalies
        WHERE tenant_id=:t AND diagnostic_run_id=:r
        ORDER BY detected_at ASC, anomaly_id ASC
    """), {'t': tenant, 'r': run_id})).mappings().all()
    relations = (await session.execute(text("""
        SELECT source_node_id AS source,target_node_id AS target,criticality,propagation_factor,relation
        FROM twin_dependency_edges
        WHERE tenant_id=:t AND active=true
    """), {'t': tenant})).mappings().all()
    chain = build_failure_chain(anomalies, relations, body.max_gap_minutes * 60.0)
    payload = to_dict(chain)
    chain_id = uuid4()
    evidence = {
        'anomaly_count': len(anomalies),
        'dependency_edge_count': len(relations),
        'max_gap_seconds': body.max_gap_minutes * 60.0,
        'method': 'temporal_dependency_evidence_v1',
        'root_cause_claim': False,
        'claim_level': chain.claim_level,
    }
    await session.execute(text("""
        INSERT INTO twin_failure_chains(
          chain_id,tenant_id,diagnostic_run_id,max_gap_seconds,chain_confidence,
          claim_level,ordered_anomalies,evidence)
        VALUES(:id,:t,:r,:gap,:c,:cl,CAST(:oa AS jsonb),CAST(:e AS jsonb))
        ON CONFLICT(tenant_id,diagnostic_run_id) DO UPDATE SET
          created_at=now(),max_gap_seconds=EXCLUDED.max_gap_seconds,
          chain_confidence=EXCLUDED.chain_confidence,claim_level=EXCLUDED.claim_level,
          ordered_anomalies=EXCLUDED.ordered_anomalies,evidence=EXCLUDED.evidence
        RETURNING chain_id
    """), {'id': chain_id, 't': tenant, 'r': run_id, 'gap': body.max_gap_minutes*60.0,
            'c': chain.confidence, 'cl': chain.claim_level, 'oa': json.dumps(payload['ordered_anomalies']), 'e': json.dumps(evidence)})
    stored_id = await session.scalar(text(
        'SELECT chain_id FROM twin_failure_chains WHERE tenant_id=:t AND diagnostic_run_id=:r'
    ), {'t': tenant, 'r': run_id})
    await session.execute(text('DELETE FROM twin_failure_chain_links WHERE tenant_id=:t AND chain_id=:c'), {'t': tenant, 'c': stored_id})
    for link in chain.links:
        await session.execute(text("""
            INSERT INTO twin_failure_chain_links(
              tenant_id,chain_id,source_anomaly_id,target_anomaly_id,relation,
              time_gap_seconds,dependency_factor,confidence,evidence)
            VALUES(:t,:c,:s,:d,:rel,:gap,:dep,:conf,CAST(:e AS jsonb))
        """), {'t':tenant,'c':stored_id,'s':UUID(link.source_anomaly),'d':UUID(link.target_anomaly),
                'rel':link.relation,'gap':link.time_gap_seconds,'dep':link.dependency_factor,
                'conf':link.confidence,'e':json.dumps(list(link.evidence))})
    await session.commit()
    return {'chain_id': str(stored_id), 'diagnostic_run_id': str(run_id), **payload, 'evidence': evidence}


@router.get('/diagnostics/{run_id}/failure-chain/explain')
async def explain_failure_chain(
    run_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant = UUID(auth.tenant_id)
    chain = (await session.execute(text("""
        SELECT * FROM twin_failure_chains
        WHERE tenant_id=:t AND diagnostic_run_id=:r
    """), {'t':tenant,'r':run_id})).mappings().first()
    if not chain:
        raise HTTPException(404, 'FAILURE_CHAIN_NOT_FOUND')
    links = (await session.execute(text("""
        SELECT * FROM twin_failure_chain_links
        WHERE tenant_id=:t AND chain_id=:c
        ORDER BY confidence DESC, time_gap_seconds ASC
    """), {'t':tenant,'c':chain['chain_id']})).mappings().all()
    return {'chain':dict(chain),'links':[dict(x) for x in links],
            'interpretation': 'correlation/dependency evidence only; root cause is not proven automatically'}

# ---- Phase 4: openBIM / IFC / CDE / COBie ----
class IfcValidateIn(BaseModel):
    content: str = Field(min_length=32, max_length=20_000_000)
    required_entity_types: list[str] = Field(default_factory=list, max_length=100)

class IfcImportIn(IfcValidateIn):
    model_key: str = Field(min_length=1,max_length=180)
    version: str = Field(min_length=1,max_length=80)
    source_system: str = Field(default='IFC_IMPORT',max_length=120)
    lifecycle_status: str = Field(default='DRAFT',max_length=32)
    filename: str = Field(default='model.ifc',max_length=255)
    discipline: str|None = Field(default=None,max_length=80)
    originator: str|None = Field(default=None,max_length=160)
    materialize_nodes: bool = False

class CdeDocumentIn(BaseModel):
    model_version_id: UUID|None = None
    document_key: str = Field(min_length=1,max_length=240)
    filename: str = Field(min_length=1,max_length=255)
    media_type: str = Field(min_length=1,max_length=160)
    content_sha256: str = Field(min_length=64,max_length=64)
    file_size_bytes: int = Field(default=0,ge=0)
    lifecycle_state: str = Field(default='WIP',max_length=24)
    revision: str = Field(default='1',max_length=80)
    discipline: str|None = Field(default=None,max_length=80)
    originator: str|None = Field(default=None,max_length=160)
    container_path: str|None = Field(default=None,max_length=500)
    metadata: dict = Field(default_factory=dict)

class CobieAssetIn(BaseModel):
    model_version_id: UUID|None = None
    external_system: str = Field(default='COBie',max_length=120)
    external_id: str = Field(min_length=1,max_length=240)
    node_id: UUID|None = None
    name: str|None = Field(default=None,max_length=500)
    asset_type: str|None = Field(default=None,max_length=180)
    serial_number: str|None = Field(default=None,max_length=240)
    manufacturer: str|None = Field(default=None,max_length=240)
    model_number: str|None = Field(default=None,max_length=240)
    installation_date: str|None = None
    warranty_start: str|None = None
    warranty_end: str|None = None
    raw_data: dict = Field(default_factory=dict)

class IdsRequirementIn(BaseModel):
    model_version_id: UUID|None = None
    requirement_key: str = Field(min_length=1,max_length=180)
    entity_type: str = Field(min_length=1,max_length=120)
    property_name: str = Field(min_length=1,max_length=240)
    required: bool = True
    allowed_values: list[str] = Field(default_factory=list,max_length=100)

@router.post('/bim/ifc/validate')
async def validate_ifc_model(body:IfcValidateIn):
    from backend.app.modules.digital_twin.domain.ifc_ingestion import validate_ifc
    try:
        return validate_ifc(body.content,required_types=body.required_entity_types)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc

@router.post('/bim/ifc/import',status_code=201)
async def import_ifc_model(body:IfcImportIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    import json
    from backend.app.modules.digital_twin.domain.ifc_ingestion import parse_ifc_step
    try: parsed=parse_ifc_step(body.content)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    tenant=UUID(auth.tenant_id)
    existing=await session.scalar(text('SELECT id FROM twin_model_versions WHERE tenant_id=:t AND model_key=:k AND version=:v'),{'t':tenant,'k':body.model_key,'v':body.version})
    if existing: raise HTTPException(409,'IFC_MODEL_VERSION_ALREADY_EXISTS')
    mv=(await session.execute(text("""INSERT INTO twin_model_versions(tenant_id,model_key,version,source_system,source_format,lifecycle_status,schema_uri,source_revision,content_sha256,metadata)
        VALUES(:t,:k,:v,:ss,:sf,:ls,:su,:sr,:sha,CAST(:m AS jsonb)) RETURNING id"""),{
        't':tenant,'k':body.model_key,'v':body.version,'ss':body.source_system,'sf':parsed['schema'] or 'IFC-STEP','ls':body.lifecycle_status,
        'su':'https://www.iso.org/standard/84123.html','sr':parsed['sha256'][:16],'sha':parsed['sha256'],
        'm':json.dumps({'phase4':'openbim','entity_count':parsed['entity_count'],'schema':parsed['schema']})})).scalar_one()
    doc=(await session.execute(text("""INSERT INTO twin_cde_documents(tenant_id,model_version_id,document_key,filename,media_type,content_sha256,file_size_bytes,lifecycle_state,revision,discipline,originator,metadata)
        VALUES(:t,:mv,:dk,:fn,:mt,:sha,:sz,'WIP','1',:d,:o,CAST(:m AS jsonb)) RETURNING id"""),{
        't':tenant,'mv':mv,'dk':f'{body.model_key}:{body.version}','fn':body.filename,'mt':'application/x-step',
        'sha':parsed['sha256'],'sz':len(body.content.encode('utf-8')),'d':body.discipline,'o':body.originator,'m':json.dumps({'ifc_schema':parsed['schema']})})).scalar_one()
    entities=parsed['entities_dict']; id_to_node={}
    _raw=body.content.encode('utf-8')
    await session.execute(text('INSERT INTO twin_model_files(tenant_id,model_version_id,filename,size_bytes,content_sha256,content) VALUES(:t,:mv,:fn,:sz,:sha,:c)'),{'t':tenant,'mv':mv,'fn':body.filename,'sz':len(_raw),'sha':parsed['sha256'],'c':_raw})
    for e in entities:
        node_id=None
        if body.materialize_nodes and e['global_id'] and e['entity_type'] not in {'IFCRELAGGREGATES','IFCRELCONTAINEDINSPATIALSTRUCTURE','IFCRELDEFINESBYPROPERTIES'}:
            node_id=await session.scalar(text('SELECT id FROM twin_nodes WHERE tenant_id=:t AND code=:c'),{'t':tenant,'c':f"IFC:{e['global_id']}"})
            if not node_id:
                node_id=(await session.execute(text("""INSERT INTO twin_nodes(tenant_id,node_type,code,name,status,metadata) VALUES(:t,:ty,:c,:n,'unknown',CAST(:m AS jsonb)) RETURNING id"""),{
                    't':tenant,'ty':e['entity_type'].lower(),'c':f"IFC:{e['global_id']}",'n':e['name'] or e['global_id'],'m':json.dumps({'ifc_global_id':e['global_id'],'model_version_id':str(mv)})})).scalar_one()
            id_to_node[e['express_id']]=node_id
            await session.execute(text("""INSERT INTO twin_bindings(tenant_id,node_id,model_version_id,identifier_system,identifier_type,identifier,confidence,metadata)
              VALUES(:t,:n,:mv,'IFC','GUID',:gid,1.0,CAST(:m AS jsonb)) ON CONFLICT DO NOTHING"""),{'t':tenant,'n':node_id,'mv':mv,'gid':e['global_id'],'m':json.dumps({'ifc_entity':e['entity_type']})})
        await session.execute(text("""INSERT INTO twin_ifc_entities(tenant_id,model_version_id,express_id,entity_type,global_id,name,object_type,attributes,properties,node_id)
            VALUES(:t,:mv,:x,:et,:gid,:n,:ot,CAST(:a AS jsonb),CAST(:p AS jsonb),:nid)"""),{
            't':tenant,'mv':mv,'x':e['express_id'],'et':e['entity_type'],'gid':e['global_id'],'n':e['name'],'ot':e['object_type'],
            'a':json.dumps(list(parsed['by_id'][e['express_id']].args)),'p':json.dumps(e['properties']),'nid':node_id})
    for rel_type, label in [('aggregates','aggregates'),('contains','contains'),('defines_properties','defines_properties')]:
        for rid,typ,a,b in [r for r in parsed['relations'] if r[1]==rel_type]:
            await session.execute(text("""INSERT INTO twin_ifc_relations(tenant_id,model_version_id,express_id,relation_type,from_express_id,to_express_id,metadata)
                VALUES(:t,:mv,:x,:r,:a,:b,CAST(:m AS jsonb)) ON CONFLICT DO NOTHING"""),{'t':tenant,'mv':mv,'x':rid,'r':label,'a':a,'b':b,'m':json.dumps({})})
            if a in id_to_node and b in id_to_node and label in {'aggregates','contains'}:
                await session.execute(text("""INSERT INTO twin_edges(tenant_id,from_node,to_node,relation,metadata) VALUES(:t,:a,:b,:r,CAST(:m AS jsonb)) ON CONFLICT DO NOTHING"""),{'t':tenant,'a':id_to_node[a],'b':id_to_node[b],'r':f'IFC_{label}','m':json.dumps({'model_version_id':str(mv)})})
    await session.commit()
    return {'model_version_id':str(mv),'cde_document_id':str(doc),'schema':parsed['schema'],'entity_count':parsed['entity_count'],'relation_count':len(parsed['relations']),'materialized_nodes':len(id_to_node),'sha256':parsed['sha256']}

@router.post('/bim/cde/documents',status_code=201)
async def register_cde_document(body:CdeDocumentIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    import json
    if body.lifecycle_state not in {'WIP','SHARED','PUBLISHED','ARCHIVED'}: raise HTTPException(422,'invalid CDE lifecycle state')
    tenant=UUID(auth.tenant_id)
    row=(await session.execute(text("""INSERT INTO twin_cde_documents(tenant_id,model_version_id,document_key,filename,media_type,content_sha256,file_size_bytes,lifecycle_state,revision,discipline,originator,container_path,metadata,published_at)
        VALUES(:t,:mv,:k,:f,:mt,:sha,:sz,:ls,:r,:d,:o,:p,CAST(:m AS jsonb),:pub) RETURNING id"""),{
        't':tenant,'mv':body.model_version_id,'k':body.document_key,'f':body.filename,'mt':body.media_type,'sha':body.content_sha256,'sz':body.file_size_bytes,
        'ls':body.lifecycle_state,'r':body.revision,'d':body.discipline,'o':body.originator,'p':body.container_path,'m':json.dumps(body.metadata),'pub':(__import__('datetime').datetime.now(__import__('datetime').timezone.utc) if body.lifecycle_state=='PUBLISHED' else None)})).scalar_one()
    await session.commit(); return {'id':str(row),'status':'registered'}

@router.post('/bim/cobie/assets',status_code=201)
async def register_cobie_asset(body:CobieAssetIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    import json
    tenant=UUID(auth.tenant_id)
    row=(await session.execute(text("""INSERT INTO twin_cobie_assets(tenant_id,model_version_id,external_system,external_id,node_id,name,asset_type,serial_number,manufacturer,model_number,installation_date,warranty_start,warranty_end,raw_data)
        VALUES(:t,:mv,:es,:eid,:nid,:n,:at,:sn,:m,:mn,CAST(NULLIF(:i,'') AS date),CAST(NULLIF(:ws,'') AS date),CAST(NULLIF(:we,'') AS date),CAST(:raw AS jsonb)) RETURNING id"""),{
        't':tenant,'mv':body.model_version_id,'es':body.external_system,'eid':body.external_id,'nid':body.node_id,'n':body.name,'at':body.asset_type,'sn':body.serial_number,
        'm':body.manufacturer,'mn':body.model_number,'i':body.installation_date,'ws':body.warranty_start,'we':body.warranty_end,'raw':json.dumps(body.raw_data)})).scalar_one()
    await session.commit(); return {'id':str(row),'status':'registered'}

@router.post('/bim/ids/requirements',status_code=201)
async def create_ids_requirement(body:IdsRequirementIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    import json
    tenant=UUID(auth.tenant_id)
    row=(await session.execute(text("""INSERT INTO twin_ids_requirements(tenant_id,model_version_id,requirement_key,entity_type,property_name,required,allowed_values)
        VALUES(:t,:mv,:k,:et,:pn,:r,CAST(:av AS jsonb)) RETURNING id"""),{'t':tenant,'mv':body.model_version_id,'k':body.requirement_key,'et':body.entity_type.upper(),'pn':body.property_name,'r':body.required,'av':json.dumps(body.allowed_values)})).scalar_one()
    await session.commit(); return {'id':str(row),'status':'created'}

class CobieImportIn(BaseModel):
    model_version_id: UUID|None = None
    content: str = Field(min_length=2,max_length=10_000_000)
    external_system: str = Field(default='COBie',max_length=120)

@router.post('/bim/cobie/import',status_code=201)
async def import_cobie_assets(body:CobieImportIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    import json
    from backend.app.modules.digital_twin.domain.cobie import parse_cobie_asset_csv
    try: rows=parse_cobie_asset_csv(body.content)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    tenant=UUID(auth.tenant_id); inserted=0; duplicates=0
    for r in rows:
        try:
            await session.execute(text("""INSERT INTO twin_cobie_assets(tenant_id,model_version_id,external_system,external_id,name,asset_type,serial_number,manufacturer,model_number,installation_date,warranty_start,warranty_end,raw_data)
              VALUES(:t,:mv,:es,:eid,:n,:at,:sn,:m,:mn,CAST(NULLIF(:i,'') AS date),CAST(NULLIF(:ws,'') AS date),CAST(NULLIF(:we,'') AS date),CAST(:raw AS jsonb))"""),{
              't':tenant,'mv':body.model_version_id,'es':r['ExternalSystem'] or body.external_system,'eid':r['ExternalId'],'n':r['Name'],'at':r['AssetType'] or None,
              'sn':r['SerialNumber'] or None,'m':r['Manufacturer'] or None,'mn':r['ModelNumber'] or None,'i':r['InstallationDate'],'ws':r['WarrantyStart'],'we':r['WarrantyEnd'],'raw':json.dumps(r)})
            inserted+=1
        except Exception:
            await session.rollback(); duplicates+=1
    await session.commit()
    return {'status':'imported','inserted':inserted,'duplicates_or_rejected':duplicates}

@router.post('/bim/ids/validate/{model_version_id}')
async def validate_ids_model(model_version_id:UUID,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    import json
    from backend.app.modules.digital_twin.domain.bim_quality import InformationRequirement, evaluate_requirements
    tenant=UUID(auth.tenant_id)
    exists=await session.scalar(text('SELECT 1 FROM twin_model_versions WHERE tenant_id=:t AND id=:mv'),{'t':tenant,'mv':model_version_id})
    if not exists: raise HTTPException(404,'model version not found')
    reqs=(await session.execute(text('SELECT * FROM twin_ids_requirements WHERE tenant_id=:t AND (model_version_id IS NULL OR model_version_id=:mv) ORDER BY requirement_key'),{'t':tenant,'mv':model_version_id})).mappings().all()
    ents=(await session.execute(text('SELECT express_id,entity_type,properties FROM twin_ifc_entities WHERE tenant_id=:t AND model_version_id=:mv ORDER BY express_id'),{'t':tenant,'mv':model_version_id})).mappings().all()
    requirements=[InformationRequirement(r['entity_type'],r['property_name'],r['required'],tuple(json.loads(r['allowed_values']) if isinstance(r['allowed_values'],str) else r['allowed_values'])) for r in reqs]
    entities=[dict(e) for e in ents]
    results=evaluate_requirements(entities,requirements)
    by_key={r['requirement_key']:r['id'] for r in reqs}
    for result in results:
        matching=[e for e in entities if e['entity_type']==result.entity_type]
        for e in (matching or [None]):
            rid=next((r['id'] for r in reqs if r['entity_type']==result.entity_type and r['property_name']==result.property_name),None)
            if rid:
                await session.execute(text("""INSERT INTO twin_ids_results(tenant_id,model_version_id,requirement_id,express_id,status,reason) VALUES(:t,:mv,:rid,:eid,:s,:reason)"""),{'t':tenant,'mv':model_version_id,'rid':rid,'eid':e['express_id'] if e else None,'s':result.status,'reason':result.reason})
    await session.commit()
    return {'model_version_id':str(model_version_id),'checked':len(results),'pass':sum(x.status=='PASS' for x in results),'fail':sum(x.status=='FAIL' for x in results),'not_applicable':sum(x.status=='NOT_APPLICABLE' for x in results)}


class IfcSpatialImportIn(BaseModel):
    model_version_id: UUID
    content_base64: str = Field(min_length=32, max_length=30_000_000)
    coordinate_system: str|None = Field(default=None,max_length=160)

class CobieXlsxAuditIn(BaseModel):
    model_version_id: UUID|None = None
    filename: str = Field(default='COBie.xlsx',max_length=255)
    content_base64: str = Field(min_length=32,max_length=30_000_000)

@router.post('/bim/ifc/spatial/import',status_code=201)
async def import_ifc_spatial(body:IfcSpatialImportIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    import base64,json
    from backend.app.modules.digital_twin.domain.ifc_ingestion import parse_ifc_step
    from backend.app.modules.digital_twin.domain.bim_geometry import extract_placements,validate_spatial_model
    tenant=UUID(auth.tenant_id)
    exists=await session.scalar(text('SELECT 1 FROM twin_model_versions WHERE tenant_id=:t AND id=:mv'),{'t':tenant,'mv':body.model_version_id})
    if not exists: raise HTTPException(404,'MODEL_VERSION_NOT_FOUND')
    try: raw=base64.b64decode(body.content_base64,validate=True); parsed=parse_ifc_step(raw.decode('utf-8'))
    except Exception as exc: raise HTTPException(422,f'INVALID_IFC:{exc}') from exc
    check=validate_spatial_model(parsed)
    if not check['valid']: raise HTTPException(422,{'code':'INVALID_IFC_SPATIAL_MODEL','details':check})
    geo=extract_placements(parsed); inserted_p=inserted_s=inserted_l=0
    for eid,v in geo['placements'].items():
        await session.execute(text("""INSERT INTO twin_ifc_placements(tenant_id,model_version_id,express_id,placement_express_id,parent_placement_express_id,matrix,location,coordinate_system) VALUES(:t,:mv,:e,:p,:pp,CAST(:m AS jsonb),CAST(:l AS jsonb),:cs) ON CONFLICT(tenant_id,model_version_id,express_id) DO UPDATE SET placement_express_id=EXCLUDED.placement_express_id,parent_placement_express_id=EXCLUDED.parent_placement_express_id,matrix=EXCLUDED.matrix,location=EXCLUDED.location,coordinate_system=EXCLUDED.coordinate_system"""),{'t':tenant,'mv':body.model_version_id,'e':eid,'p':v['placement_id'],'pp':geo['local_placements'].get(v['placement_id'],{}).get('parent'),'m':json.dumps(v['matrix']),'l':json.dumps({'x':v['location'][0],'y':v['location'][1],'z':v['location'][2]}),'cs':body.coordinate_system}); inserted_p+=1
    for e in geo['spatial_elements']:
        node=await session.scalar(text('SELECT id FROM twin_nodes WHERE tenant_id=:t AND code=:c'),{'t':tenant,'c':f"IFC:{e['global_id']}"}) if e.get('global_id') else None
        await session.execute(text("""INSERT INTO twin_ifc_spatial_context(tenant_id,model_version_id,express_id,spatial_type,global_id,name,floorplan_node_id,metadata) VALUES(:t,:mv,:e,:st,:gid,:n,:fn,CAST(:m AS jsonb)) ON CONFLICT(tenant_id,model_version_id,express_id) DO UPDATE SET spatial_type=EXCLUDED.spatial_type,name=EXCLUDED.name,floorplan_node_id=EXCLUDED.floorplan_node_id,metadata=EXCLUDED.metadata"""),{'t':tenant,'mv':body.model_version_id,'e':e['express_id'],'st':e['entity_type'],'gid':e['global_id'],'n':e['name'],'fn':node,'m':json.dumps({'floorplan_link':'IFC_GUID_MATCH' if node else 'UNRESOLVED'})}); inserted_s+=1
    for rel in geo['containment']:
        await session.execute(text("""INSERT INTO twin_ifc_spatial_links(tenant_id,model_version_id,relation_express_id,relation_type,from_express_id,to_express_id,metadata) VALUES(:t,:mv,:r,:rt,:a,:b,CAST(:m AS jsonb)) ON CONFLICT DO NOTHING"""),{'t':tenant,'mv':body.model_version_id,'r':rel['relation_express_id'],'rt':rel['relation_type'],'a':rel['from_express_id'],'b':rel['to_express_id'],'m':json.dumps({'coordinate_system':body.coordinate_system})}); inserted_l+=1
    await session.commit(); return {'model_version_id':str(body.model_version_id),'schema':parsed['schema'],'sha256':parsed['sha256'],'validation':check,'placements':inserted_p,'spatial_contexts':inserted_s,'spatial_links':inserted_l}

@router.post('/bim/cobie/xlsx/audit',status_code=201)
async def audit_cobie_xlsx(body:CobieXlsxAuditIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    import base64,hashlib,json
    from backend.app.modules.digital_twin.domain.cobie_xlsx import parse_cobie_xlsx
    try: raw=base64.b64decode(body.content_base64,validate=True); result=parse_cobie_xlsx(raw)
    except Exception as exc: raise HTTPException(422,f'INVALID_COBIE_XLSX:{exc}') from exc
    tenant=UUID(auth.tenant_id); sha=hashlib.sha256(raw).hexdigest()
    audit=(await session.execute(text("""INSERT INTO twin_cobie_xlsx_audits(tenant_id,model_version_id,filename,content_sha256,valid,sheet_names,missing_required_sheets,component_count,components_missing_name,metadata) VALUES(:t,:mv,:f,:sha,:v,CAST(:s AS jsonb),CAST(:m AS jsonb),:c,:cm,CAST(:meta AS jsonb)) RETURNING id"""),{'t':tenant,'mv':body.model_version_id,'f':body.filename,'sha':sha,'v':result['valid'],'s':json.dumps(result['sheet_names']),'m':json.dumps(result['missing_required_sheets']),'c':result['component_count'],'cm':result['components_missing_name'],'meta':json.dumps({'phase4':'cobie_xlsx_audit'})})).scalar_one()
    await session.commit(); return {'audit_id':str(audit),'sha256':sha,**{k:v for k,v in result.items() if k!='rows'}}

class CdeTransitionIn(BaseModel):
    target_state: str = Field(min_length=3,max_length=24)

@router.post('/bim/cde/documents/{document_id}/transition')
async def transition_cde_document(document_id:UUID,body:CdeTransitionIn,auth:AuthContext=Depends(get_auth_context),session:AsyncSession=Depends(get_tenant_session)):
    tenant=UUID(auth.tenant_id); target=body.target_state.upper()
    allowed={'WIP':{'SHARED'},'SHARED':{'PUBLISHED','WIP'},'PUBLISHED':{'ARCHIVED'},'ARCHIVED':set()}
    current=await session.scalar(text('SELECT lifecycle_state FROM twin_cde_documents WHERE tenant_id=:t AND id=:id'),{'t':tenant,'id':document_id})
    if current is None: raise HTTPException(404,'CDE document not found')
    if target not in allowed.get(current,set()): raise HTTPException(409,f'invalid CDE transition {current}->{target}')
    await session.execute(text("UPDATE twin_cde_documents SET lifecycle_state=:s,published_at=CASE WHEN :ispub THEN now() ELSE published_at END WHERE tenant_id=:t AND id=:id"),{'s':target,'ispub':target=='PUBLISHED','t':tenant,'id':document_id})
    await session.commit(); return {'id':str(document_id),'from':current,'to':target}
