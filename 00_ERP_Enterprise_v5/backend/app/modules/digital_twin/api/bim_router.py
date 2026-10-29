"""Endpoints de lectura para el Centro de Mando BIM (visor 3D + gemelo). Aditivo: no altera router.py."""
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session

router = APIRouter(prefix='/digital-twin', tags=['digital-twin-bim'])

def _t(auth: AuthContext) -> UUID: return UUID(auth.tenant_id)

@router.get('/overview')
async def overview(auth: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_tenant_session)):
    t = {'t': _t(auth)}
    one = lambda sql: session.execute(text(sql), t)
    nodes = (await one("SELECT node_type, count(*) c FROM twin_nodes WHERE tenant_id=:t GROUP BY 1")).all()
    pts = (await one("""SELECT count(*) total,
        count(*) FILTER (WHERE s.point_id IS NULL) never,
        count(*) FILTER (WHERE s.point_id IS NOT NULL AND now()-s.observed_at > make_interval(secs => p.stale_after_seconds)) stale,
        count(*) FILTER (WHERE s.quality IN ('GOOD','VALID') AND now()-s.observed_at <= make_interval(secs => p.stale_after_seconds)) good
        FROM twin_points p LEFT JOIN twin_point_states s ON s.tenant_id=p.tenant_id AND s.point_id=p.id WHERE p.tenant_id=:t""")).mappings().one()
    dev = (await one("SELECT count(*) total, count(*) FILTER (WHERE status='ONLINE') online FROM twin_devices WHERE tenant_id=:t")).mappings().one()
    an = (await one("SELECT severity, count(*) c FROM operational_anomalies WHERE tenant_id=:t AND status='open' GROUP BY 1")).all()
    health = (await one("SELECT avg(health_score) avg, min(health_score) min, count(*) n FROM twin_health_assessments WHERE tenant_id=:t")).mappings().one()
    bim = (await one("""SELECT (SELECT count(*) FROM twin_model_versions WHERE tenant_id=:t) models,
        (SELECT count(*) FROM twin_ifc_entities WHERE tenant_id=:t) entities,
        (SELECT count(*) FROM twin_ids_results WHERE tenant_id=:t AND status='PASS') ids_pass,
        (SELECT count(*) FROM twin_ids_results WHERE tenant_id=:t AND status='FAIL') ids_fail,
        (SELECT count(*) FROM twin_bindings WHERE tenant_id=:t AND identifier_system='IFC') bindings,
        (SELECT count(*) FROM twin_nodes WHERE tenant_id=:t AND code LIKE 'IFC:%') ifc_nodes""")).mappings().one()
    wo = (await one("SELECT count(*) FROM twin_maintenance_work_requests WHERE tenant_id=:t AND status='PENDING'")).scalar_one()
    return {'nodes_by_type': {r[0]: r[1] for r in nodes}, 'nodes_total': sum(r[1] for r in nodes),
            'points': dict(pts), 'devices': dict(dev), 'open_anomalies_by_severity': {r[0]: r[1] for r in an},
            'open_anomalies': sum(r[1] for r in an),
            'health': {'avg': float(health['avg']) if health['avg'] is not None else None, 'min': float(health['min']) if health['min'] is not None else None, 'assessed_nodes': health['n']},
            'bim': dict(bim), 'pending_work_requests': wo}

@router.get('/anomalies')
async def anomalies(limit: int = Query(50, ge=1, le=500), status: str | None = None, auth: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_tenant_session)):
    q = """SELECT a.anomaly_id,a.node_id,n.name node_name,n.code node_code,a.metric,a.severity,a.status,a.score,a.observed_value,a.baseline_value,
           a.diagnostic_confidence,a.probable_causes,a.diagnostic_run_id,a.detected_at FROM operational_anomalies a
           LEFT JOIN twin_nodes n ON n.id=a.node_id WHERE a.tenant_id=:t"""
    p = {'t': _t(auth), 'l': limit}
    if status: q += ' AND a.status=:s'; p['s'] = status
    return [dict(r) for r in (await session.execute(text(q + ' ORDER BY a.detected_at DESC LIMIT :l'), p)).mappings().all()]

@router.get('/points')
async def list_points(node_id: UUID | None = None, limit: int = Query(200, ge=1, le=1000), auth: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_tenant_session)):
    q = """SELECT p.id,p.node_id,p.code,p.name,p.semantic_kind,p.canonical_unit,p.engineering_min,p.engineering_max,p.stale_after_seconds,
           s.value,s.unit,s.quality,s.quality_reason,s.observed_at,
           CASE WHEN s.point_id IS NULL THEN 'NO_DATA' WHEN now()-s.observed_at > make_interval(secs => p.stale_after_seconds) THEN 'STALE' ELSE 'FRESH' END freshness
           FROM twin_points p LEFT JOIN twin_point_states s ON s.tenant_id=p.tenant_id AND s.point_id=p.id WHERE p.tenant_id=:t"""
    prm = {'t': _t(auth), 'l': limit}
    if node_id: q += ' AND p.node_id=:n'; prm['n'] = node_id
    return [dict(r) for r in (await session.execute(text(q + ' ORDER BY p.code LIMIT :l'), prm)).mappings().all()]

@router.get('/points/{point_id}/series')
async def point_series(point_id: UUID, minutes: int = Query(60, ge=1, le=10080), auth: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_tenant_session)):
    rows = (await session.execute(text("""SELECT observed_at, canonical_value value, quality FROM twin_telemetry_samples
        WHERE tenant_id=:t AND point_id=:p AND observed_at >= now() - make_interval(mins => :m) ORDER BY observed_at ASC LIMIT 2000"""),
        {'t': _t(auth), 'p': point_id, 'm': minutes})).mappings().all()
    return [dict(r) for r in rows]

@router.get('/model-versions')
async def model_versions(auth: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_tenant_session)):
    rows = (await session.execute(text("""SELECT v.id,v.model_key,v.version,v.source_format,v.lifecycle_status,v.content_sha256,v.created_at,
        (f.id IS NOT NULL) has_file, f.filename, f.size_bytes,
        (SELECT count(*) FROM twin_ifc_entities e WHERE e.tenant_id=v.tenant_id AND e.model_version_id=v.id) entity_count
        FROM twin_model_versions v LEFT JOIN twin_model_files f ON f.tenant_id=v.tenant_id AND f.model_version_id=v.id
        WHERE v.tenant_id=:t ORDER BY v.created_at DESC"""), {'t': _t(auth)})).mappings().all()
    return [dict(r) for r in rows]

@router.get('/model-versions/{model_version_id}/file')
async def model_file(model_version_id: UUID, auth: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_tenant_session)):
    row = (await session.execute(text("SELECT filename,media_type,content,content_sha256 FROM twin_model_files WHERE tenant_id=:t AND model_version_id=:m"),
                                 {'t': _t(auth), 'm': model_version_id})).mappings().first()
    if not row: raise HTTPException(404, 'MODEL_FILE_NOT_FOUND')
    return Response(bytes(row['content']), media_type=row['media_type'],
                    headers={'ETag': row['content_sha256'], 'Content-Disposition': f'inline; filename="{row["filename"]}"', 'Cache-Control': 'private, max-age=300'})

@router.get('/bim/lookup')
async def lookup_by_global_id(global_id: str = Query(min_length=1, max_length=64), auth: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_tenant_session)):
    row = (await session.execute(text("""SELECT n.id node_id,n.node_type,n.code,n.name,n.status FROM twin_bindings b JOIN twin_nodes n ON n.id=b.node_id
        WHERE b.tenant_id=:t AND b.identifier_system='IFC' AND b.identifier=:g
        ORDER BY (n.node_type LIKE 'ifc%') ASC, b.confidence DESC, n.updated_at DESC, n.id LIMIT 1"""), {'t': _t(auth), 'g': global_id})).mappings().first()
    # Prioridad: el nodo OPERATIVO enlazado a la geometría (equipo con salud/telemetría/anomalías) gana al nodo técnico creado por la importación IFC.
    if not row: raise HTTPException(404, 'NO_TWIN_NODE_FOR_GLOBAL_ID')
    return dict(row)

@router.get('/nodes/{node_id}/detail')
async def node_detail(node_id: UUID, auth: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_tenant_session)):
    t = _t(auth)
    node = (await session.execute(text("SELECT id,parent_id,node_type,code,name,status,metadata FROM twin_nodes WHERE tenant_id=:t AND id=:n"), {'t': t, 'n': node_id})).mappings().first()
    if not node: raise HTTPException(404, 'TWIN_NODE_NOT_FOUND')
    g = lambda sql: session.execute(text(sql), {'t': t, 'n': node_id})
    return {
        'node': dict(node),
        'health': next(iter((await g("SELECT health_score,severity,confidence,assessed_at FROM twin_health_assessments WHERE tenant_id=:t AND node_id=:n")).mappings().all()), None),
        'points': [dict(r) for r in (await g("""SELECT p.id,p.code,p.name,p.semantic_kind,p.canonical_unit,s.value,s.quality,s.observed_at FROM twin_points p
                    LEFT JOIN twin_point_states s ON s.tenant_id=p.tenant_id AND s.point_id=p.id WHERE p.tenant_id=:t AND p.node_id=:n ORDER BY p.code""")).mappings().all()],
        'anomalies': [dict(r) for r in (await g("SELECT anomaly_id,metric,severity,status,score,diagnostic_confidence,probable_causes,detected_at FROM operational_anomalies WHERE tenant_id=:t AND node_id=:n ORDER BY detected_at DESC LIMIT 20")).mappings().all()],
        'bindings': [dict(r) for r in (await g("SELECT identifier_system,identifier_type,identifier,confidence FROM twin_bindings WHERE tenant_id=:t AND node_id=:n")).mappings().all()],
        'ifc': next(iter((await g("SELECT e.express_id,e.entity_type,e.global_id,e.properties FROM twin_ifc_entities e WHERE e.tenant_id=:t AND (e.node_id=:n OR e.global_id IN (SELECT b.identifier FROM twin_bindings b WHERE b.tenant_id=:t AND b.node_id=:n AND b.identifier_system='IFC')) ORDER BY (e.node_id=:n) DESC LIMIT 1")).mappings().all()), None),
        'dependencies': {'upstream': [dict(r) for r in (await g("SELECT source_node_id,relation,criticality FROM twin_dependency_edges WHERE tenant_id=:t AND target_node_id=:n AND active")).mappings().all()],
                         'downstream': [dict(r) for r in (await g("SELECT target_node_id,relation,criticality FROM twin_dependency_edges WHERE tenant_id=:t AND source_node_id=:n AND active")).mappings().all()]},
    }


_MAINT_ES = {'CONDITION_BASED': 'basado en condición', 'PREVENTIVE': 'preventivo', 'CORRECTIVE': 'correctivo', 'PREDICTIVE': 'predictivo', 'INSPECTION': 'de inspección'}
_CLAIM_ES = {'correlation_with_dependency_evidence': 'correlación con evidencia de dependencias', 'temporal_precedence_only': 'solo precedencia temporal', 'causal_hypothesis': 'hipótesis causal'}
_pretty = lambda v, m: m.get(str(v), str(v).replace('_', ' ').lower())


@router.get('/nodes/{node_id}/timeline')
async def node_timeline(node_id: UUID, auth: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_tenant_session)):
    """Flujo operativo de un equipo, en orden cronológico: anomalía -> diagnóstico -> cadena de falla -> orden de mantenimiento -> SST de la zona
    (actividades SST cuya zone_id es el propio nodo o uno de sus ancestros espaciales). Todo viene de la base; nada se simula."""
    t = {'t': _t(auth), 'n': node_id}
    if not (await session.execute(text('SELECT 1 FROM twin_nodes WHERE tenant_id=:t AND id=:n'), t)).first(): raise HTTPException(404, 'node not found')
    rows = lambda sql: session.execute(text(sql), t)
    steps: list[dict] = []
    for r in (await rows("""SELECT anomaly_id,metric,severity,status,observed_value,baseline_value,diagnostic_run_id,detected_at FROM operational_anomalies
            WHERE tenant_id=:t AND node_id=:n ORDER BY detected_at DESC LIMIT 20""")).mappings():
        steps.append({'at': r['detected_at'], 'kind': 'anomaly', 'ref': str(r['anomaly_id']), 'severity': r['severity'], 'state': 'active' if r['status'] == 'open' else 'completed',
                      'title': f"Anomalía detectada: {r['metric']}", 'detail': f"Observado {r['observed_value']:.4g} frente a base {r['baseline_value']:.4g}" if r['observed_value'] is not None and r['baseline_value'] is not None else r['metric']})
    runs = (await rows("""SELECT diagnostic_run_id,method,health_score,severity,confidence,created_at FROM twin_diagnostic_runs
            WHERE tenant_id=:t AND node_id=:n ORDER BY created_at DESC LIMIT 10""")).mappings().all()
    for r in runs:
        steps.append({'at': r['created_at'], 'kind': 'diagnosis', 'ref': str(r['diagnostic_run_id']), 'severity': r['severity'], 'state': 'completed',
                      'title': 'Diagnóstico ejecutado', 'detail': f"Método {r['method']} · salud {r['health_score']:.0f} · confianza {r['confidence']:.2f}"})
    run_ids = [r['diagnostic_run_id'] for r in runs]
    if run_ids:
        for r in (await session.execute(text("""SELECT chain_id,diagnostic_run_id,chain_confidence,claim_level,created_at FROM twin_failure_chains
                WHERE tenant_id=:t AND diagnostic_run_id = ANY(:r) ORDER BY created_at DESC"""), {'t': t['t'], 'r': run_ids})).mappings():
            steps.append({'at': r['created_at'], 'kind': 'failure_chain', 'ref': str(r['chain_id']), 'severity': None, 'state': 'completed',
                          'title': 'Cadena de falla inferida', 'detail': f"Afirmación: {_pretty(r['claim_level'], _CLAIM_ES)}" + (f" · confianza {r['chain_confidence']:.2f}" if r['chain_confidence'] else '')})
    for r in (await rows("""SELECT request_id,maintenance_type,severity,estimated_cost,approval_required,status,created_at FROM twin_maintenance_work_requests
            WHERE tenant_id=:t AND (asset_id=:n OR asset_id IN (
                SELECT CAST(b.identifier AS uuid) FROM twin_bindings b WHERE b.tenant_id=:t AND b.node_id=:n AND lower(b.identifier_type) IN ('asset_id','asset')
                AND b.identifier ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'))
            ORDER BY created_at DESC LIMIT 10""")).mappings():
        needs = bool(r['approval_required']) and str(r['status']).upper() == 'PENDING'
        steps.append({'at': r['created_at'], 'kind': 'work_request', 'ref': str(r['request_id']), 'severity': r['severity'], 'state': 'pending' if needs else 'completed',
                      'title': f"Orden de mantenimiento {_pretty(r['maintenance_type'], _MAINT_ES)}", 'detail': ('Requiere aprobación humana' if needs else 'Aprobada') + (f" · costo estimado {r['estimated_cost']:,.0f}" if r['estimated_cost'] else '')})
    for r in (await rows("""WITH RECURSIVE anc AS (SELECT id,parent_id FROM twin_nodes WHERE tenant_id=:t AND id=:n
            UNION ALL SELECT p.id,p.parent_id FROM twin_nodes p JOIN anc a ON p.id=a.parent_id WHERE p.tenant_id=:t)
            SELECT a.id,a.activity_type,a.risk_level,a.status,a.start_at,a.updated_at FROM sst_activities a
            WHERE a.tenant_id=:t AND a.zone_id IN (SELECT id FROM anc) ORDER BY a.updated_at DESC LIMIT 10""")).mappings():
        st = str(r['status'])
        steps.append({'at': r['updated_at'], 'kind': 'sst', 'ref': str(r['id']), 'severity': r['risk_level'], 'state': 'blocked' if st == 'blocked' else ('completed' if st == 'approved' else 'active'),
                      'title': f"SST · {r['activity_type']}", 'detail': f"Riesgo {r['risk_level']} · estado {st}"})
    steps.sort(key=lambda s: s['at'])
    return {'node_id': str(node_id), 'steps': steps}


@router.get('/bim/health-map')
async def health_map(auth: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_tenant_session)):
    """Salud por GlobalId IFC en UNA consulta (el visor tiñe todo el modelo con esto). Si un GUID tiene un nodo operativo enlazado, gana sobre el nodo técnico de la importación."""
    rows = (await session.execute(text("""
        SELECT b.identifier AS global_id, n.id AS node_id, n.name, n.node_type, h.health_score, h.severity AS health_severity,
               (SELECT count(*) FROM operational_anomalies a WHERE a.tenant_id=:t AND a.node_id=n.id AND a.status='open') AS open_anomalies,
               (SELECT a.severity FROM operational_anomalies a WHERE a.tenant_id=:t AND a.node_id=n.id AND a.status='open'
                 ORDER BY CASE a.severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END LIMIT 1) AS worst_severity
        FROM twin_bindings b JOIN twin_nodes n ON n.id=b.node_id AND n.tenant_id=b.tenant_id
        LEFT JOIN twin_health_assessments h ON h.node_id=n.id AND h.tenant_id=n.tenant_id
        WHERE b.tenant_id=:t AND b.identifier_system='IFC' AND (n.node_type NOT LIKE 'ifc%' OR NOT EXISTS (
              SELECT 1 FROM twin_bindings b2 JOIN twin_nodes n2 ON n2.id=b2.node_id AND n2.tenant_id=b2.tenant_id
              WHERE b2.tenant_id=:t AND b2.identifier_system='IFC' AND b2.identifier=b.identifier AND n2.node_type NOT LIKE 'ifc%'))
        ORDER BY b.identifier LIMIT 5000"""), {'t': _t(auth)})).mappings().all()
    return [{'global_id': r['global_id'], 'node_id': str(r['node_id']), 'name': r['name'], 'node_type': r['node_type'], 'health_score': r['health_score'],
             'health_severity': r['health_severity'], 'open_anomalies': r['open_anomalies'], 'worst_severity': r['worst_severity']} for r in rows]
