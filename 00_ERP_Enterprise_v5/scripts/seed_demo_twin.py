"""Siembra un gemelo de demostración COMPLETO usando solo la API (sin SQL): jerarquía espacial, equipos, sensores, telemetría, diagnóstico,
cadena de falla, orden de mantenimiento, IFC real con enlaces GUID->equipo y una actividad SST bloqueada en la zona.
Uso: python scripts/seed_demo_twin.py --base http://127.0.0.1:8000 --tenant <uuid> --email admin@x.co --password ... [--ifc samples/torre_demo.ifc]"""
from __future__ import annotations
import argparse, json, sys, urllib.error, urllib.request, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

PUMP_GUID, TANK_GUID = "3tQ5UgSD11VOwa7ZfyDW$n", "13bz5Kktn94Ay9K8f9y71Q"

class Api:
    def __init__(self, base: str): self.base, self.token = base.rstrip("/"), ""
    def call(self, method: str, path: str, body=None, ok=(200, 201, 204), soft=False):
        req = urllib.request.Request(f"{self.base}/api/v1{path}", method=method, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {self.token}"} if self.token else {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as r: raw = r.read(); return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode()[:200]
            if soft: print(f"  (omitido {method} {path}: {e.code} {detail})"); return None
            raise SystemExit(f"{method} {path} -> {e.code} {detail}")

def seed(base: str, tenant: str, email: str, password: str, ifc_path: str) -> dict:
    a = Api(base); a.token = a.call("POST", "/auth/login", {"email": email, "password": password, "tenant_id": tenant})["access_token"]
    T = "/digital-twin"; now = datetime.now(timezone.utc)
    site = a.call("POST", f"{T}/nodes", {"node_type": "site", "code": "S1", "name": "Conjunto Altos del Parque"})["id"]
    bld = a.call("POST", f"{T}/nodes", {"node_type": "building", "code": "T1", "name": "Torre 1", "parent_id": site})["id"]
    pump = a.call("POST", f"{T}/nodes", {"node_type": "equipment", "code": "P1", "name": "Bomba de presurización B1", "parent_id": bld})["id"]
    tank = a.call("POST", f"{T}/nodes", {"node_type": "equipment", "code": "TK1", "name": "Tanque de agua T1", "parent_id": bld})["id"]
    for f, t in ((site, bld), (bld, pump), (bld, tank)): a.call("POST", f"{T}/edges", {"from_node": f, "to_node": t, "relation": "CONTAINS"})
    a.call("POST", f"{T}/dependencies", {"source_node_id": pump, "target_node_id": tank, "relation": "SUPPLIES"})
    for node, code, series in ((pump, "temp-p1", [40, 42, 46, 55, 70, 90]), (tank, "temp-tk1", [21, 21.4, 21.2, 21.6, 21.3, 21.5])):
        dev = a.call("POST", f"{T}/devices", {"node_id": node, "device_type": "sensor", "external_device_id": f"dev-{code}"})["id"]
        pt = a.call("POST", f"{T}/points", {"node_id": node, "device_id": dev, "code": code, "name": "Temperatura", "semantic_kind": "temperature", "canonical_unit": "degC", "engineering_min": 0, "engineering_max": 120})["id"]
        for i, v in enumerate(series):
            a.call("POST", f"{T}/telemetry/samples", {"point_id": pt, "value": v, "unit": "degC", "observed_at": (now - timedelta(minutes=(len(series) - 1 - i) * 5 + 1)).isoformat(), "source": "demo", "source_message_id": f"{code}-{i}", "sequence": i})
    out = {"site": site, "building": bld, "pump": pump, "tank": tank}
    for node, label in ((pump, "pump"), (tank, "tank")):
        run = a.call("POST", f"{T}/diagnostics/evaluate", {"node_id": node, "window_minutes": 120, "min_samples": 3})["diagnostic_run_id"]; out[f"run_{label}"] = run
        if label == "pump":
            a.call("POST", f"{T}/diagnostics/{run}/enrich", {}, soft=True); a.call("POST", f"{T}/diagnostics/{run}/failure-chain", {"diagnostic_run_id": run}, soft=True)
    imp = a.call("POST", f"{T}/bim/ifc/import", {"content": Path(ifc_path).read_text(), "model_key": "torre", "version": "1", "materialize_nodes": True, "filename": Path(ifc_path).name})
    out["model_version_id"] = imp.get("model_version_id") or imp.get("id")
    for guid, node in ((PUMP_GUID, pump), (TANK_GUID, tank)):
        a.call("POST", f"{T}/bindings", {"node_id": node, "identifier_system": "IFC", "identifier_type": "GUID", "identifier": guid})
    # La orden de mantenimiento exige un vínculo EXPLÍCITO con el registro de activos (nunca adivina a partir del id del nodo)
    a.call("POST", f"{T}/bindings", {"node_id": pump, "identifier_system": "CMMS", "identifier_type": "asset_id", "identifier": str(uuid.uuid4())})
    wr = a.call("POST", f"{T}/diagnostics/{out['run_pump']}/maintenance-work-request", {}, soft=True)
    if wr: out["work_request"] = wr.get("work_request_id") or wr.get("request_id") or wr.get("id") or wr
    # SST: regla que exige certificado + actividad en la zona (la torre) => la evaluación bloquea
    a.call("POST", "/sst/master/rules", {"jurisdiction": "CO", "activity_type": "mantenimiento_bombas", "rule_key": "bombas-co", "definition": {"requirements": [
        {"key": "cert_mantenimiento", "evidence_type": "certificado_mantenimiento", "mandatory": True, "severity": "alto", "scope": "contractor"}]}}, soft=True)
    act = a.call("POST", "/sst/activities", {"zone_id": bld, "activity_type": "mantenimiento_bombas", "jurisdiction": "CO", "risk_level": "alto", "contractor_id": str(uuid.uuid4()),
                 "start_at": (now + timedelta(hours=2)).isoformat(), "end_at": (now + timedelta(hours=8)).isoformat()}, soft=True)
    if act:
        aid = act.get("id") or act.get("activity_id"); out["sst_activity"] = aid; a.call("POST", f"/sst/activities/{aid}/evaluate", {}, soft=True)
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for k in ("base", "tenant", "email", "password"): ap.add_argument(f"--{k}", required=True)
    ap.add_argument("--ifc", default=str(Path(__file__).resolve().parents[1] / "samples" / "torre_demo.ifc"))
    r = ap.parse_args(); print(json.dumps(seed(r.base, r.tenant, r.email, r.password, r.ifc), indent=1))
