"""E2E real: FastAPI + PostgreSQL 16 (RLS con rol NO superusuario). Se omite si no hay PHASE13_DATABASE_URL."""
import asyncio, os, pathlib, uuid
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.engine import make_url

URL = os.getenv("PHASE13_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="requiere PostgreSQL real (PHASE13_DATABASE_URL)")
ROOT = pathlib.Path(__file__).resolve().parents[3]
MIGS = [ROOT/"backend/app/modules/digital_twin/migrations/001_outbox_events.sql", *sorted((ROOT/"migrations/sql").glob("2026*.sql"))]
import pathlib as _p
CSV = "ExternalSystem,ExternalId,Name,AssetType,SerialNumber,Manufacturer,ModelNumber,InstallationDate,WarrantyStart,WarrantyEnd\nCOBie,A2,Valvula,Valve,SN1,ACME,M1,2026-02-01,2026-02-01,2028-02-01\n"
IFC = ("ISO-10303-21;HEADER;FILE_SCHEMA(('IFC4X3_ADD2'));ENDSEC;DATA;#1=IFCPROJECT('0PROJ',$,'Project',$,$,$,$,(#2),$);"
       "#2=IFCSITE('0SITE',$,'Site',$,$,$,$,$,.ELEMENT.,$,$,$,$,$);#3=IFCBUILDING('0BLDG',$,'Building',$,$,$,$,$,.ELEMENT.,$,$);"
       "#4=IFCSPACE('0SP',$,'Room 101',$,$,$,$,$,.ELEMENT.,$);#5=IFCRELAGGREGATES('0REL',$,$,$,#1,(#2));"
       "#6=IFCRELAGGREGATES('0REL2',$,$,$,#2,(#3));ENDSEC;END-ISO-10303-21;")

@pytest.fixture(scope="module")
def client():
    import asyncpg
    from fastapi.testclient import TestClient
    raw = URL.replace("postgresql+asyncpg://", "postgresql://", 1)
    async def prep():
        c = await asyncpg.connect(raw)
        await c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        for m in MIGS: await c.execute(m.read_text())
        await c.execute("DO $$BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='erp_app') THEN CREATE ROLE erp_app LOGIN PASSWORD 'erp_app' NOSUPERUSER NOBYPASSRLS; END IF; END$$;"
                        "GRANT ALL ON ALL TABLES IN SCHEMA public TO erp_app; GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO erp_app; GRANT USAGE ON SCHEMA public TO erp_app;")
        await c.close()
    asyncio.run(prep())
    os.environ["DATABASE_URL"] = make_url(raw).set(drivername="postgresql+asyncpg", username="erp_app", password="erp_app").render_as_string(hide_password=False)
    os.environ["JWT_SECRET_KEY"] = "x" * 48
    from backend.app.main import app
    with TestClient(app) as c:
        yield c

def hdr(tenant):
    from backend.app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token(str(uuid.uuid4()), tenant, ["admin"])}

def test_full_twin_flow(client):
    A, B = str(uuid.uuid4()), str(uuid.uuid4()); ha, hb = hdr(A), hdr(B)
    assert client.get("/readyz").status_code == 200
    P = "/api/v1/digital-twin"
    def post(path, body, h=ha, code=201):
        r = client.post(P+path, json=body, headers=h); assert r.status_code == code, (path, r.status_code, r.text); return r.json()
    site = post("/nodes", {"node_type":"site","code":"S1","name":"Conjunto"})["id"]
    bld = post("/nodes", {"node_type":"building","code":"T1","name":"Torre 1","parent_id":site})["id"]
    pump = post("/nodes", {"node_type":"equipment","code":"P1","name":"Bomba 1","parent_id":bld})["id"]
    post("/edges", {"from_node":bld,"to_node":pump,"relation":"CONTAINS"})
    g = client.get(P+"/graph", headers=ha).json()
    assert len(g["nodes"]) == 3 and len(g["edges"]) == 1
    assert client.get(P+"/graph", headers=hb).json() == {"nodes": [], "edges": []}   # RLS / aislamiento
    dev = post("/devices", {"node_id":pump,"device_type":"sensor","external_device_id":"dev-1"})["id"]
    pt = post("/points", {"node_id":pump,"device_id":dev,"code":"temp","name":"Temp","semantic_kind":"temperature","canonical_unit":"degC","engineering_min":0,"engineering_max":100})["id"]
    now = datetime.now(timezone.utc)
    for i, v in enumerate([40, 42, 46, 55, 120, 150]):
        s = post("/telemetry/samples", {"point_id":pt,"value":v,"unit":"degC","observed_at":(now-timedelta(minutes=30-i*5)).isoformat(),"source":"t","source_message_id":f"m{i}","sequence":i,"source_quality":"BAD"})
        assert s["status"] == "accepted"
    assert post("/telemetry/samples", {"point_id":pt,"value":150,"unit":"degC","observed_at":now.isoformat(),"source":"t","source_message_id":"m5"}, code=201)["status"] == "duplicate"
    batch = {"samples":[
        {"point_id":pt,"value":91,"unit":"degC","observed_at":now.isoformat(),"source":"batch","source_message_id":"batch-1","sequence":10,"source_quality":"BAD"},
        {"point_id":pt,"value":92,"unit":"degC","observed_at":(now+timedelta(seconds=1)).isoformat(),"source":"batch","source_message_id":"batch-2","sequence":11,"source_quality":"BAD"},
    ]}
    batch_response = client.post(P+"/telemetry/samples/batch", json=batch, headers=ha)
    assert batch_response.status_code == 202, batch_response.text
    assert batch_response.json()["accepted"] == 2
    replay = client.post(P+"/telemetry/samples/batch", json=batch, headers=ha)
    assert replay.status_code == 202 and replay.json()["accepted"] == 0
    changed = {"samples":[{**batch["samples"][0],"value":99}]}
    conflict = client.post(P+"/telemetry/samples/batch", json=changed, headers=ha)
    assert conflict.status_code == 409, conflict.text
    cross_tenant = client.post(P+"/telemetry/samples/batch", json=batch, headers=hb)
    assert cross_tenant.status_code == 404
    invalid_atomic_batch = {"samples":[
        {"point_id":pt,"value":93,"unit":"degC","observed_at":now.isoformat(),"source":"batch","source_message_id":"atomic-good","source_quality":"BAD"},
        {"point_id":str(uuid.uuid4()),"value":94,"unit":"degC","observed_at":now.isoformat(),"source":"batch","source_message_id":"atomic-missing-point"},
    ]}
    assert client.post(P+"/telemetry/samples/batch", json=invalid_atomic_batch, headers=ha).status_code == 404
    assert client.post(P+"/telemetry/samples/batch", json={"samples":[invalid_atomic_batch["samples"][0]]}, headers=ha).json()["accepted"] == 1
    assert client.get(f"{P}/points/{pt}/latest", headers=ha).json()["value"] is not None
    run = post("/diagnostics/evaluate", {"node_id":pump,"window_minutes":120,"min_samples":3})
    assert run["anomalies_created_or_updated"] >= 1, run
    rid = run["diagnostic_run_id"]
    assert client.get(f"{P}/diagnostics/{rid}/explain", headers=ha).status_code == 200
    r = client.post(f"{P}/diagnostics/{rid}/enrich", json={}, headers=ha); assert r.status_code == 200, r.text
    post(f"/diagnostics/{rid}/failure-chain", {"diagnostic_run_id":rid})
    post("/dependencies", {"source_node_id":pump,"target_node_id":bld,"relation":"SUPPLIES"})
    post("/diagnostics/system", {"system_node_id":site})
    # IFC
    v = client.post(P+"/bim/ifc/validate", json={"content":IFC,"required_entity_types":["IFCBUILDING"]}, headers=ha); assert v.status_code == 200 and v.json()["valid"]
    imp = post("/bim/ifc/import", {"content":IFC,"model_key":"m","version":"1","materialize_nodes":True})
    assert client.get(P+"/graph", headers=ha).json()["nodes"].__len__() > 3
    mvid = imp.get("model_version_id") or imp.get("id")
    import base64, hashlib
    doc = post("/bim/cde/documents", {"model_version_id":mvid,"document_key":"DOC1","filename":"a.ifc","media_type":"application/x-step","content_sha256":hashlib.sha256(b"a").hexdigest()})
    r = client.post(f"{P}/bim/cde/documents/{doc['id']}/transition", json={"target_state":"SHARED"}, headers=ha); assert r.status_code == 200, r.text
    post("/bim/cobie/assets", {"model_version_id":mvid,"external_id":"A1","name":"Bomba","installation_date":"2026-01-15","warranty_start":"2026-01-15","warranty_end":"2028-01-15"})
    post("/bim/cobie/import", {"model_version_id":mvid,"content":CSV})
    post("/bim/ids/requirements", {"model_version_id":mvid,"requirement_key":"R1","entity_type":"ifcspace","property_name":"Name"})
    r = client.post(f"{P}/bim/ids/validate/{mvid}", headers=ha); assert r.status_code in (200, 201), r.text
    r = client.post(P+"/bim/ifc/spatial/import", json={"model_version_id":mvid,"content_base64":base64.b64encode(IFC.encode()).decode()}, headers=ha); assert r.status_code == 201, r.text
    r = client.post(f"{P}/diagnostics/{rid}/maintenance-work-request", json={}, headers=ha); assert r.status_code in (201, 422), r.text
    # ---- IFC real con geometría + endpoints del Centro de Mando ----
    real = (ROOT/"frontend"/"bim"/"public"/"torre_demo.ifc").read_text()
    demo = post("/bim/ifc/import", {"content":real,"model_key":"torre","version":"1","materialize_nodes":True,"filename":"torre_demo.ifc"})
    dmv = demo.get("model_version_id") or demo.get("id")
    f = client.get(f"{P}/model-versions/{dmv}/file", headers=ha); assert f.status_code == 200 and f.content.decode() == real
    assert client.get(f"{P}/model-versions/{dmv}/file", headers=hb).status_code == 404       # aislamiento
    mvs = client.get(P+"/model-versions", headers=ha).json(); assert any(m["has_file"] and m["entity_count"] >= 30 for m in mvs)
    lk = client.get(P+"/bim/lookup", params={"global_id":"3tQ5UgSD11VOwa7ZfyDW$n"}, headers=ha); assert lk.status_code == 200, lk.text
    assert lk.json()["name"] == "Bomba de presurización B1"
    det = client.get(f"{P}/nodes/{lk.json()['node_id']}/detail", headers=ha).json()
    assert det["ifc"]["entity_type"] == "IFCPUMP" and det["ifc"]["properties"]["Pset_ManufacturerTypeInformation.Manufacturer"] == "ACME"
    healthy_sample = post("/telemetry/samples", {
        "point_id": pt, "value": 55, "unit": "degC",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source": "dashboard-health-check", "source_message_id": "dashboard-valid-sample",
        "source_quality": "GOOD",
    })
    assert healthy_sample["quality"] == "VALID"
    ov = client.get(P+"/overview", headers=ha).json()
    assert ov["nodes_total"] > 30 and ov["points"]["total"] == 1 and ov["bim"]["models"] == 2 and ov["devices"]["online"] == 1
    assert ov["points"]["good"] == 1
    assert ov["open_anomalies"] >= 1 and ov["health"]["avg"] is not None
    an = client.get(P+"/anomalies", headers=ha).json(); assert an and an[0]["node_name"] == "Bomba 1"
    assert len(client.get(f"{P}/points/{pt}/series", params={"minutes":120}, headers=ha).json()) == 9
    assert client.get(P+"/points", params={"node_id":pump}, headers=ha).json()[0]["freshness"] in ("FRESH","STALE")
    assert client.get(P+"/overview", headers=hb).json()["nodes_total"] == 0
    # --- FORMA de las respuestas que lee el visor (frontend/bim/src/main.ts): si el API cambia un campo, esto falla antes que el navegador ---
    need = lambda d, *ks: [k for k in ks if k not in d]
    assert not need(ov, "nodes_total", "bim", "points", "devices", "open_anomalies", "health", "pending_work_requests")
    assert not need(ov["bim"], "models", "entities", "ids_pass", "ids_fail") and not need(ov["points"], "good", "total") and not need(ov["devices"], "online", "total") and "avg" in ov["health"]
    assert not need(det, "node", "health", "points", "anomalies", "dependencies", "ifc") and not need(det["node"], "name", "node_type", "code", "status")
    assert not need(det["dependencies"], "upstream", "downstream") and not need(det["ifc"], "global_id", "entity_type", "properties")
    assert all(not need(p_, "id", "name", "value", "canonical_unit") for p_ in det["points"]) and all(not need(a_, "metric", "severity") for a_ in det["anomalies"])
    assert all(not need(a_, "node_id", "severity", "metric") and ("node_name" in a_ or "node_code" in a_) for a_ in an)
    assert all(not need(m_, "id", "model_key", "version", "has_file", "entity_count") for m_ in mvs)
    assert all("value" in s_ for s_ in client.get(f"{P}/points/{pt}/series", params={"minutes": 120}, headers=ha).json())
    assert "node_id" in lk.json()
    # --- CONEXIÓN geometría <-> gemelo operativo: enlazar el GUID IFC al equipo con telemetría. El clic en el 3D debe llevar al equipo (salud/puntos/anomalías), no al nodo técnico del IFC ---
    assert lk.json()["node_type"] == "ifcpump" and lk.json()["node_id"] != pump, "sin enlace, el clic cae en el nodo técnico del IFC"
    post("/bindings", {"node_id": pump, "identifier_system": "IFC", "identifier_type": "GUID", "identifier": "3tQ5UgSD11VOwa7ZfyDW$n"})
    lk2 = client.get(P+"/bim/lookup", params={"global_id": "3tQ5UgSD11VOwa7ZfyDW$n"}, headers=ha).json()
    assert lk2["node_id"] == pump and lk2["node_type"] == "equipment", "con enlace, el clic resuelve al equipo operativo"
    det2 = client.get(f"{P}/nodes/{pump}/detail", headers=ha).json()
    assert det2["health"] and det2["points"] and det2["anomalies"], "el equipo enlazado trae salud, puntos y anomalías"
    assert det2["ifc"]["entity_type"] == "IFCPUMP" and det2["ifc"]["properties"]["Pset_ManufacturerTypeInformation.Manufacturer"] == "ACME", "y las propiedades IFC por el vínculo"
    hm = {e["global_id"]: e for e in client.get(P+"/bim/health-map", headers=ha).json()}
    assert hm["3tQ5UgSD11VOwa7ZfyDW$n"]["node_id"] == pump and hm["3tQ5UgSD11VOwa7ZfyDW$n"]["health_score"] is not None and hm["3tQ5UgSD11VOwa7ZfyDW$n"]["open_anomalies"] >= 1, "el mapa de salud tiñe la bomba (operativa) con su salud y anomalías"
    assert all(not need(e, "global_id", "node_id", "name", "node_type", "health_score", "health_severity", "open_anomalies", "worst_severity") for e in hm.values()) and len({e["global_id"] for e in hm.values()}) == len(hm), "un solo registro por GlobalId"


def test_visor_bim_servido_por_fastapi(client):
    """El visor compilado (frontend/dist/bim) se sirve en /bim y el WASM de web-ifc con MIME correcto."""
    dist = ROOT / "frontend" / "dist" / "bim"
    if not dist.is_dir():
        pytest.skip("ejecuta `npm run build:bim` en frontend/ antes")
    from backend.app.main import app
    assert any(getattr(r, "path", "") == "/bim" for r in app.routes), "main.py no montó /bim"
    r = client.get("/bim/"); assert r.status_code == 200 and "BIM Twin PRO" in r.text and all(i in r.text for i in ("id=\"cv\"", "id=\"ifc-tree\"", "tab-workflow", "knowledge-canvas")), "la página del Centro de Mando trae visor, árbol, grafo y flujo"
    w = client.get("/bim/web-ifc.wasm"); assert w.status_code == 200 and w.headers["content-type"].startswith("application/wasm") and w.content[:4] == b"\x00asm"
    assert client.get("/bim/torre_demo.ifc").status_code == 200
    js = [p.name for p in (dist / "assets").glob("*.js")]; assert any(n.startswith("three-") for n in js) and any(n.startswith("ifc-") for n in js)


def test_contrato_visor_bim_vs_api():
    """Cada ruta que usa frontend/bim/src/api.ts debe existir en el API (método incluido): el visor no puede quedar apuntando a rutas fantasma."""
    import re
    from backend.app.main import app
    paths = set(app.openapi()["paths"])
    src = (ROOT / "frontend" / "bim" / "src" / "api.ts").read_text()
    used = set()
    for m in re.finditer(r"[`\"](/[A-Za-z0-9_\-/{}$.]*)(?:\?[^`\"]*)?[`\"]", src):
        p = re.sub(r"\$\{[^}]*\}", "{x}", m.group(1))
        if p.startswith("/") and len(p) > 1 and not p.startswith("/api/") and p != "/": used.add(p)
    assert used, "no se extrajo ninguna ruta"
    norm = lambda s: re.sub(r"\{[^}]*\}", "{x}", s)
    api_paths = {norm(p) for p in paths}
    missing = sorted(p for p in used if f"/api/v1/digital-twin{p}" not in api_paths and norm(f"/api/v1{p}") not in api_paths)
    assert not missing, f"rutas del visor que NO existen en el API: {missing}"
    assert "/api/v1/auth/login" in api_paths
