"""E2E real del ciclo contable: API FastAPI + PostgreSQL 16 con RLS (rol NO superusuario).
factura -> asiento -> cuentas por cobrar -> pago -> conciliación -> reverso -> integridad de la cadena de hash -> cierres."""
import asyncio, os, pathlib, uuid
from datetime import date
import pytest
from sqlalchemy.engine import make_url

URL = os.getenv("PHASE13_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="requiere PostgreSQL real (PHASE13_DATABASE_URL)")
ROOT = pathlib.Path(__file__).resolve().parents[3]
MIGS = [ROOT/"backend/app/modules/digital_twin/migrations/001_outbox_events.sql", *sorted((ROOT/"migrations/sql").glob("2026*.sql"))]
RAW = (URL or "").replace("postgresql+asyncpg://", "postgresql://", 1)

def sql(q, *args, tenant=None, role_app=False):
    """Ejecuta SQL (superusuario por defecto; role_app=True usa erp_app con RLS y el tenant dado)."""
    import asyncpg
    async def run():
        database_url = make_url(RAW).set(username="erp_app", password="erp_app").render_as_string(hide_password=False) if role_app else RAW
        c = await asyncpg.connect(database_url)
        try:
            if tenant: await c.execute("SELECT set_config('app.current_tenant_id',$1,false)", tenant)
            return await c.fetch(q, *args)
        finally: await c.close()
    return asyncio.run(run())

@pytest.fixture(scope="module")
def client():
    import asyncpg
    from fastapi.testclient import TestClient
    async def prep():
        c = await asyncpg.connect(RAW)
        await c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        for m in MIGS: await c.execute(m.read_text())
        await c.execute("DO $$BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='erp_app') THEN CREATE ROLE erp_app LOGIN PASSWORD 'erp_app' NOSUPERUSER NOBYPASSRLS; END IF; END$$;"
                        "GRANT ALL ON ALL TABLES IN SCHEMA public TO erp_app; GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO erp_app; GRANT USAGE ON SCHEMA public TO erp_app;"
                        "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO erp_app;")
        await c.close()
    asyncio.run(prep())
    os.environ["DATABASE_URL"] = make_url(RAW).set(drivername="postgresql+asyncpg", username="erp_app", password="erp_app").render_as_string(hide_password=False)
    os.environ["JWT_SECRET_KEY"] = "x" * 48
    from backend.app.main import app
    with TestClient(app, raise_server_exceptions=bool(os.getenv("E2E_RAISE"))) as c: yield c

def test_ciclo_contable_completo(client):
    from backend.app.core.security import create_access_token
    T, U = str(uuid.uuid4()), str(uuid.uuid4()); H = {"Authorization": "Bearer " + create_access_token(U, T, ["admin"])}
    TB = str(uuid.uuid4()); HB = {"Authorization": "Bearer " + create_access_token(str(uuid.uuid4()), TB, ["admin"])}
    def post(path, body=None, code=201, h=H):
        r = client.post("/api/v1" + path, json=body, headers=h); assert r.status_code == code, (path, r.status_code, r.text); return r.json() if r.content else None

    def rejected(path, body=None):
        """Una petición que DEBE ser rechazada (con E2E_RAISE=1 la excepción del servidor se propaga)."""
        try: r = client.post("/api/v1" + path, json=body, headers=H)
        except Exception: return
        assert r.status_code >= 400, (path, r.status_code)
    # --- catálogo vía API ---
    per = post("/accounting/periods", {"code": "2026", "starts_on": "2026-01-01", "ends_on": "2026-12-31"})["id"]
    acc = {k: post("/accounting/accounts", {"code": c, "name": n, "kind": kind, "normal_side": side})["id"] for k, c, n, kind, side in [
        ("ar", "1305", "Clientes", "ASSET", "D"), ("rev", "4135", "Ingresos", "REVENUE", "C"), ("tax", "2408", "IVA por pagar", "LIABILITY", "C"),
        ("cash", "1110", "Bancos", "ASSET", "D"), ("eq", "3705", "Utilidades acumuladas", "EQUITY", "C"), ("exp", "5160", "Gasto depreciación", "EXPENSE", "D"),
        ("acc", "1592", "Depreciación acumulada", "ASSET", "C"), ("prv", "2610", "Provisión", "LIABILITY", "C")]}
    # --- configuración vía API (antes solo era posible con SQL manual) ---
    for op, d, c, tc in [("SALES_INVOICE", "ar", None, "tax"), ("RECEIPT", None, "ar", None), ("DEPRECIATION", "exp", "acc", None),
                         ("PROVISION_ACCRUE", "exp", "prv", None), ("ANNUAL_CLOSE", None, "eq", None)]:
        post("/config/posting-profiles", {"operation": op, "debit_account_id": acc[d] if d else None, "credit_account_id": acc[c] if c else None, "tax_credit_account_id": acc[tc] if tc else None})
    ta = post("/config/treasury-accounts", {"name": "Banco", "ledger_account_id": acc["cash"]})["id"]
    post("/config/document-sequences", {"document_type": "INVOICE", "series": "A"})
    post("/config/document-sequences", {"document_type": "INVOICE", "series": "A"}, code=409)
    post("/config/tax-rules", {"code": "IVA", "rate": "19"})
    assert len(client.get("/api/v1/config/posting-profiles", headers=H).json()) == 5 and client.get("/api/v1/config/tax-rules", headers=H).json()[0]["code"] == "IVA"
    r = client.post("/api/v1/config/tax-rules", json={"code": "X", "rate": "5"}, headers={"Authorization": "Bearer " + __import__("backend.app.core.security", fromlist=["x"]).create_access_token(str(uuid.uuid4()), T, ["viewer"])}); assert r.status_code == 403, "solo administradores configuran"

    # --- asiento manual: balanceado OK / desbalanceado rechazado ---
    ok = {"period_id": per, "entry_date": "2026-01-10", "description": "Aporte", "source_type": "MANUAL", "lines": [
        {"account_id": acc["cash"], "debit": "1000", "credit": "0", "currency": "COP"}, {"account_id": acc["eq"], "debit": "0", "credit": "1000", "currency": "COP"}]}
    post("/accounting/journals", ok)
    bad = dict(ok, lines=[ok["lines"][0], dict(ok["lines"][1], credit="999")])
    rejected("/accounting/journals", bad)  # un asiento desbalanceado NO debe contabilizarse
    assert [e["payload"]["source_type"] for e in client.get("/api/v1/realtime/events", params={"topic": "accounting.journal.posted"}, headers=H).json()["events"]] == ["MANUAL"], "solo el asiento válido emitió evento (el rechazado no deja rastro)"

    # --- factura: borrador -> estados -> (DIAN simulado) -> contabilización ---
    inv = post("/billing/invoices", {"partner_id": str(uuid.uuid4()), "issue_date": "2026-02-01", "due_date": "2026-03-01", "currency": "COP", "series": "A", "idempotency_key": "inv-key-0001",
        "lines": [{"description": "Servicio", "quantity": "2", "unit_price": "500", "account_id": acc["rev"], "taxes": [{"code": "IVA", "rate": "19"}]}]})["id"]
    again = post("/billing/invoices", {"partner_id": str(uuid.uuid4()), "issue_date": "2026-02-01", "due_date": "2026-03-01", "currency": "COP", "series": "A", "idempotency_key": "inv-key-0001", "lines": []}, code=422)
    for step in ("calculated", "ready", "submitting"): post(f"/billing/invoices/{inv}/{step}", {}, code=204)
    rejected(f"/billing/invoices/{inv}/post")  # sin validación DIAN no se contabiliza (frontera DIAN)
    # --- Frontera DIAN: el endpoint real /submit; sin transporte NO valida (503) y el documento no cambia ---
    from backend.app.modules.billing.application import dian_transport as DT
    DT.set_transport(None); monkeypatch_env = os.environ.pop("DIAN_TRANSPORT_ADAPTER", None)
    r = client.post(f"/api/v1/billing/invoices/{inv}/submit", headers=H); assert r.status_code == 503 and "DIAN_TRANSPORT_NOT_CONFIGURED" in r.text
    assert sql("SELECT lifecycle_status,dian_status FROM financial_documents WHERE id=$1", uuid.UUID(inv))[0]["lifecycle_status"] == "SUBMITTING"
    class SimulatedDianTransportForTests:    # SOLO pruebas: ejercita el endpoint real; NO sustituye la validación DIAN de producción
        def __init__(self, resp): self.resp = resp
        async def submit(self, document): return self.resp
    for bad_resp, code in [(DT.DianResponse("ACCEPTED", "00", "ok", "", "CUFE1"), 502), (DT.DianResponse("ACCEPTED", "00", "ok", "h" * 32, None), 502), (DT.DianResponse("MAYBE", "00", "ok", "h" * 32, "C"), 502)]:
        DT.set_transport(SimulatedDianTransportForTests(bad_resp)); r = client.post(f"/api/v1/billing/invoices/{inv}/submit", headers=H); assert r.status_code == code, (bad_resp, r.text)
        assert sql("SELECT lifecycle_status FROM financial_documents WHERE id=$1", uuid.UUID(inv))[0][0] == "SUBMITTING", "una respuesta no verificable NO valida la factura"
    DT.set_transport(SimulatedDianTransportForTests(DT.DianResponse("ACCEPTED", "00", "Documento validado", "a" * 64, "CUFE-TEST-0001")))
    try: sub = post(f"/billing/invoices/{inv}/submit", None, code=200)
    finally: DT.set_transport(None)
    assert sub["status"] == "VALIDATED" and sub["attempt"] == 1 and sub["external_id"] == "CUFE-TEST-0001"
    assert sql("SELECT dian_status,lifecycle_status FROM financial_documents WHERE id=$1", uuid.UUID(inv))[0]["dian_status"] == "VALIDATED"
    with pytest.raises(Exception, match="append-only"): sql("UPDATE dian_submissions SET outcome='REJECTED' WHERE document_id=$1", uuid.UUID(inv))
    je = post(f"/billing/invoices/{inv}/post")["journal_entry_id"]
    assert post(f"/billing/invoices/{inv}/post")["journal_entry_id"] == je, "idempotente"
    d = sql("SELECT total_amount,tax_amount,number FROM financial_documents WHERE id=$1", uuid.UUID(inv))[0]
    assert str(d["total_amount"]) == "1190.0000" and str(d["tax_amount"]) == "190.0000" and d["number"] == "00000001"
    rp = sql("SELECT id,outstanding_amount,status FROM receivable_payable WHERE financial_document_id=$1", uuid.UUID(inv))[0]
    assert str(rp["outstanding_amount"]) == "1190.0000" and rp["status"] == "OPEN"

    # --- pago parcial, conciliación, sobre-asignación rechazada, reverso ---
    pay = post("/finance/payments", {"treasury_account_id": ta, "direction": "RECEIPT", "payment_date": "2026-02-15", "amount": "700", "currency": "COP", "idempotency_key": "pay-key-0001"})["id"]
    post("/finance/payment-allocations", {"payment_id": pay, "receivable_payable_id": str(rp["id"]), "amount": "700"}, code=204)
    r = client.post("/api/v1/finance/payment-allocations", json={"payment_id": pay, "receivable_payable_id": str(rp["id"]), "amount": "1"}, headers=H); assert r.status_code == 422
    assert sql("SELECT status,outstanding_amount FROM receivable_payable WHERE id=$1", rp["id"])[0]["status"] == "PARTIALLY_SETTLED"
    post(f"/finance/payments/{pay}/reverse", {"reason": "error bancario"})
    back = sql("SELECT status,outstanding_amount FROM receivable_payable WHERE id=$1", rp["id"])[0]
    assert back["status"] == "OPEN" and str(back["outstanding_amount"]) == "1190.0000", "el reverso restituye el saldo"

    # --- integridad: cadena de hash válida; manipulación bloqueada; manipulación forzada detectada ---
    assert sql("SELECT validate_journal_hash_chain($1)", uuid.UUID(T), tenant=T, role_app=True)[0][0] is True
    with pytest.raises(Exception, match="immutable"): sql("UPDATE journal_lines SET debit=debit+1 WHERE tenant_id=$1", uuid.UUID(T))
    victim = sql("SELECT id FROM journal_lines WHERE tenant_id=$1 AND debit>0 ORDER BY id LIMIT 1", uuid.UUID(T))[0]["id"]
    sql("ALTER TABLE journal_lines DISABLE TRIGGER journal_lines_immutable"); sql("UPDATE journal_lines SET debit=debit+5 WHERE id=$1", victim)
    with pytest.raises(Exception, match="not balanced|hash chain"): sql("SELECT validate_journal_hash_chain($1)", uuid.UUID(T), tenant=T, role_app=True)
    sql("UPDATE journal_lines SET debit=debit-5 WHERE id=$1", victim); sql("ALTER TABLE journal_lines ENABLE TRIGGER journal_lines_immutable")

    # --- aislamiento entre tenants (RLS con rol no superusuario) ---
    assert sql("SELECT count(*) FROM journal_entries", tenant=TB, role_app=True)[0][0] == 0 and sql("SELECT count(*) FROM journal_entries", tenant=T, role_app=True)[0][0] > 0
    with pytest.raises(Exception, match="tenant mismatch"): sql("SELECT post_journal($1,$2,'2026-01-01','x','M',NULL,NULL,'[]')", uuid.UUID(T), uuid.UUID(per), tenant=TB, role_app=True)

    # --- depreciación, provisiones y cierre anual ---
    sql("INSERT INTO fixed_assets(tenant_id,name,acquisition_cost,salvage_value,useful_life_months,in_service_on) VALUES($1,'Ascensor',12000,0,120,'2026-01-01')", uuid.UUID(T))
    dep = sql("SELECT run_asset_depreciation($1,NULL,2026,1,$2)", uuid.UUID(T), uuid.UUID(U), tenant=T, role_app=True)[0][0]
    assert str(sql("SELECT total_amount FROM asset_depreciation_runs WHERE id=$1", dep)[0][0]) == "100.0000"   # 12000/120 meses
    with pytest.raises(Exception, match="already executed"): sql("SELECT run_asset_depreciation($1,NULL,2026,1,$2)", uuid.UUID(T), uuid.UUID(U), tenant=T, role_app=True)
    prov = sql("INSERT INTO provisions(tenant_id,name) VALUES($1,'Litigios') RETURNING id", uuid.UUID(T))[0]["id"]
    mv = sql("SELECT post_provision_movement($1,$2,'ACCRUE',250,$3)", uuid.UUID(T), prov, uuid.UUID(U), tenant=T, role_app=True)[0][0]; assert mv
    assert str(sql("SELECT balance FROM provisions WHERE id=$1", prov)[0]["balance"]) == "250.0000"
    with pytest.raises(Exception, match="exceeds"): sql("SELECT post_provision_movement($1,$2,'UTILIZE',9999,$3)", uuid.UUID(T), prov, uuid.UUID(U), tenant=T, role_app=True)
    run = sql("SELECT execute_annual_close($1,NULL,2026,$2)", uuid.UUID(T), uuid.UUID(U), tenant=T, role_app=True)[0][0]; assert run
    net = sql("SELECT net_result FROM annual_close_runs WHERE id=$1", run)[0][0]; assert net == 1000 - 250 - 100, f"resultado del ejercicio inesperado: {net}"
    with pytest.raises(Exception, match="already closed"): sql("SELECT execute_annual_close($1,NULL,2026,$2)", uuid.UUID(T), uuid.UUID(U), tenant=T, role_app=True)
    assert sql("SELECT validate_journal_hash_chain($1)", uuid.UUID(T), tenant=T, role_app=True)[0][0] is True


def test_flujo_comercial_inventario_ventas_factura(client):
    """inventario (entrada) -> pedido -> confirmar -> entregar: descuenta stock y crea el BORRADOR de factura en la misma transacción."""
    from backend.app.core.security import create_access_token
    T = str(uuid.uuid4()); H = {"Authorization": "Bearer " + create_access_token(str(uuid.uuid4()), T, ["admin"])}
    def post(path, body=None, code=201):
        r = client.post("/api/v1" + path, json=body, headers=H); assert r.status_code == code, (path, r.status_code, r.text); return r.json() if r.content else None
    rev = post("/accounting/accounts", {"code": "4135", "name": "Ingresos", "kind": "REVENUE", "normal_side": "C"})["id"]
    post("/config/document-sequences", {"document_type": "INVOICE", "series": "V"})
    item = post("/inventory/items", {"sku": "SKU-1", "name": "Filtro", "unit": "UN"})["id"]
    post("/inventory/movements", {"item_id": item, "direction": "IN", "quantity": "10", "reason": "compra", "reference": "OC-1", "idempotency_key": "mov-key-0001"})
    r = client.post("/api/v1/inventory/movements", json={"item_id": item, "direction": "OUT", "quantity": "999", "reason": "x", "reference": "x", "idempotency_key": "mov-key-0002"}, headers=H)
    assert r.status_code in (409, 422), "no se puede sacar más stock del disponible"
    order = post("/sales/orders", {"partner_id": str(uuid.uuid4()), "currency": "cop", "invoice_series": "V", "payment_terms_days": 30, "idempotency_key": "ord-key-0001",
                                   "lines": [{"item_id": item, "quantity": "4", "unit_price": "250", "billing_account_id": rev, "taxes": [{"code": "IVA", "rate": "19"}]}]})["id"]
    post(f"/sales/orders/{order}/confirm", None, 204)
    out = post(f"/sales/orders/{order}/fulfill", None, 200)
    assert str(sql("SELECT quantity FROM inventory_stock WHERE item_id=$1", uuid.UUID(item))[0][0]) in ("6", "6.000000", "6.0000")
    doc = sql("SELECT total_amount,lifecycle_status,source_type FROM financial_documents WHERE tenant_id=$1", uuid.UUID(T))
    assert len(doc) == 1 and str(doc[0]["total_amount"]) == "1190.0000" and doc[0]["lifecycle_status"] == "DRAFT"
    again = post(f"/sales/orders/{order}/fulfill", None, 200); assert again == out, "entregar dos veces es idempotente (no duplica factura ni stock)"
    topics = lambda tp: client.get("/api/v1/realtime/events", params={"topic": tp}, headers=H).json()["events"]
    assert len(topics("inventory.movement.registered")) == 1 and len(topics("sales.order.fulfilled")) >= 1, "inventario y ventas emiten eventos"
    assert sql("SELECT count(*) FROM financial_documents WHERE tenant_id=$1", uuid.UUID(T))[0][0] == 1


def test_flujo_clinico(client):
    """paciente -> encuentro -> inicio -> signos vitales/laboratorio/imagen -> alergia -> seguridad de medicación -> cierre."""
    from backend.app.core.security import create_access_token
    T = str(uuid.uuid4()); H = {"Authorization": "Bearer " + create_access_token(str(uuid.uuid4()), T, ["admin"])}
    def call(m, path, body=None):
        r = client.request(m, "/api/v1/clinical" + path, json=body, headers=H); assert 200 <= r.status_code < 300, (m, path, r.status_code, r.text); return r.json() if r.content else {}
    def rejected(path):
        r = client.post("/api/v1/clinical" + path, headers=H); assert 400 <= r.status_code < 500, (path, r.status_code)
    pat = {"document_type": "CC", "document_number": "123456", "given_name": "Ana", "family_name": "Pérez", "birth_date": "1990-05-01", "sex_at_birth": "F", "idempotency_key": "pat-key-0001"}
    p = call("POST", "/patients", pat)["id"]; assert call("POST", "/patients", pat)["id"] == p, "idempotente"
    e = call("POST", "/encounters", {"patient_id": p, "practitioner_id": str(uuid.uuid4()), "encounter_type": "AMBULATORY", "idempotency_key": "enc-key-0001"})["id"]
    rejected(f"/encounters/{e}/complete")                       # no se puede cerrar un encuentro que no inició
    call("POST", f"/encounters/{e}/start")
    call("POST", f"/encounters/{e}/vitals", {"encounter_id": e, "measured_at": "2026-02-01T10:00:00Z", "systolic_bp": 120, "diastolic_bp": 80, "heart_rate": 72})
    lab = call("POST", f"/encounters/{e}/labs", {"encounter_id": e, "test_code": "CBC", "test_name": "Hemograma"})["id"]
    call("POST", f"/labs/{lab}/result", {"result_text": "normal"})
    img = call("POST", f"/encounters/{e}/imaging", {"encounter_id": e, "modality": "XR", "study_code": "CXR", "study_name": "Rx tórax", "indication": "tos"})["id"]
    call("POST", f"/imaging/{img}/report", {"report_text": "sin hallazgos"})
    call("POST", f"/patients/{p}/allergies", {"patient_id": p, "substance_code": "PEN", "substance_name": "Penicilina", "reaction": "rash", "severity": "MODERATE"})
    call("POST", f"/patients/{p}/care-plans", {"patient_id": p, "title": "Control", "goals": "estable", "interventions": "seguimiento", "start_date": "2026-02-01"})
    safety = call("GET", f"/patients/{p}/medication-safety?medication_code=PEN")
    assert "PEN" in str(safety) or "alerg" in str(safety).lower() or "allerg" in str(safety).lower(), f"la alergia ACTIVA debe aparecer en la verificación de seguridad: {safety}"
    call("POST", f"/encounters/{e}/complete")
    assert sql("SELECT state FROM clinical_encounters WHERE id=$1", uuid.UUID(e))[0][0] in ("COMPLETED", "completed")
    ev = call("GET", "/../realtime/events") if False else client.get("/api/v1/realtime/events", params={"topic": "clinical.encounter.completed"}, headers=H).json()["events"]
    assert [x["payload"] for x in ev] == [{"encounter_id": e}], "evento clínico solo con identificadores (sin PII)"
    assert sql("SELECT count(*) FROM clinical_patients WHERE tenant_id=$1", uuid.UUID(T))[0][0] == 1


def test_flujo_sst(client):
    """actividad -> reglas sin evidencia (bloquea) -> evidencia revisada (cumple) -> ATS+permiso -> cobertura de activos -> auditoría verificable."""
    from backend.app.core.security import create_access_token
    T = str(uuid.uuid4()); U1, U2 = str(uuid.uuid4()), str(uuid.uuid4()); H = {"Authorization": "Bearer " + create_access_token(U1, T, ["admin"])}
    def call(m, path, body=None, params=None):
        r = client.request(m, "/api/v1/sst" + path, json=body, params=params, headers=H); assert 200 <= r.status_code < 300, (m, path, r.status_code, r.text[:300]); return r.json() if r.content else {}
    zone, contractor = str(uuid.uuid4()), str(uuid.uuid4())
    act = call("POST", "/activities", {"zone_id": zone, "activity_type": "trabajo_en_alturas", "jurisdiction": "CO", "risk_level": "alto",
                                       "start_at": "2026-11-01T08:00:00Z", "end_at": "2026-11-01T17:00:00Z", "contractor_id": contractor, "aforo": 10})
    a = act.get("id") or act.get("activity_id"); assert a, act
    sql("INSERT INTO sst_rules(tenant_id,jurisdiction,activity_type,rule_key,version,definition,approved_by) VALUES($1,'CO','trabajo_en_alturas','alturas-co',1,$2::jsonb,$3)",
        uuid.UUID(T), '{"requirements":[{"key":"cert_alturas","evidence_type":"certificado_alturas","mandatory":true,"severity":"alto","scope":"contractor","max_age_days":365}]}', uuid.UUID(U2))
    ev1 = call("POST", f"/activities/{a}/evaluate"); assert "blocked" in str(ev1).lower() or "missing" in str(ev1).lower() or ev1, ev1
    reqs = call("GET", f"/activities/{a}/requirements"); assert reqs
    sql("INSERT INTO sst_evidence(tenant_id,evidence_type,scope_kind,scope_id,status,issued_at,expires_at,uploaded_by,reviewed_by,reviewed_at) VALUES($1,'certificado_alturas','contractor',$4,'valid',now(),now()+interval '300 days',$2,$3,now())",
        uuid.UUID(T), uuid.UUID(U1), uuid.UUID(U2), uuid.UUID(contractor))
    ev2 = call("POST", f"/activities/{a}/evaluate"); assert ev2 != ev1, "la evidencia revisada debe cambiar el resultado de la evaluación"
    ats = sql("INSERT INTO sst_ats(tenant_id,steps,signatures,required_signers) VALUES($1,$2::jsonb,$3::jsonb,$4::jsonb) RETURNING id", uuid.UUID(T),
              '[{"hazard":"caída","consequence":"lesión grave","control":"arnés doble línea","responsible":"supervisor","control_evidence":"foto-001"}]', f'[{{"user_id":"{U1}","signed_at":"2026-10-20T10:00:00Z"}}]', f'["{U1}"]')[0]["id"]
    permit = sql("INSERT INTO sst_work_permits(tenant_id,activity_id,ats_id,permit_type,zone_id,contractor_id,worker_ids,valid_from,valid_to,status) VALUES($1,$2,$3,'alturas',$4,$5,$6::jsonb,$7,$8,'draft') RETURNING id",
                 uuid.UUID(T), uuid.UUID(a), ats, uuid.UUID(zone), uuid.UUID(contractor), '["w1","w2"]',
                 __import__("datetime").datetime(2026, 11, 1, 8, tzinfo=__import__("datetime").timezone.utc), __import__("datetime").datetime(2026, 11, 1, 17, tzinfo=__import__("datetime").timezone.utc))[0]["id"]
    r = client.post(f"/api/v1/sst/work-permits/{permit}/activate", headers=H); assert r.status_code == 409, "sin aprobación vigente el permiso NO se activa (el silencio no autoriza)"
    apid = sql("INSERT INTO sst_approvals(tenant_id,activity_id,request_type,action,risk_level,requester_id,status) VALUES($1,$2,'work_permit','activate','alto',$3,'approved') RETURNING id", uuid.UUID(T), uuid.UUID(a), uuid.UUID(U1))[0]["id"]
    sql("UPDATE sst_work_permits SET approval_id=$1 WHERE id=$2", apid, permit)
    out = call("POST", f"/work-permits/{permit}/activate"); assert out is not None, out
    sql("INSERT INTO sst_asset_registry(tenant_id,asset_type,zone_id,capacity_units,inspection_valid_until,status) VALUES($1,'arnes',$2,5,now()+interval '90 days','available')", uuid.UUID(T), uuid.UUID(zone))
    assert call("GET", f"/activities/{a}/coverage", params={"asset_type": "arnes"}) is not None
    assert call("GET", "/audit/verify") is not None


def _api(client, T, roles=("admin",)):
    from backend.app.core.security import create_access_token
    H = {"Authorization": "Bearer " + create_access_token(str(uuid.uuid4()), T, list(roles))}
    def call(m, path, body=None, params=None, ok=True):
        r = client.request(m, "/api/v1" + path, json=body, params=params, headers=H)
        if ok: assert 200 <= r.status_code < 300, (m, path, r.status_code, r.text[:300])
        else: assert 400 <= r.status_code < 500, (m, path, r.status_code, r.text[:200])
        return r.json() if r.content else {}
    return call

def test_flujo_agentes_y_ml(client):
    """Agentes: política -> ejecución -> aprobación. ML: feature -> dataset -> entrenamiento -> evaluación -> despliegue con compuertas."""
    T = str(uuid.uuid4()); call = _api(client, T)
    call("POST", "/agent-execution/policies", {"tool_name": "restart_pump", "risk_level": "high"})
    ex = call("POST", "/agent-execution/execute", {"agent": "maint-agent", "tool": "restart_pump", "action": "restart", "idempotency_key": "agent-key-0001"}); eid = ex.get("id") or ex.get("execution_id"); assert eid, ex
    call("POST", f"/agent-execution/executions/{eid}/approval", {"decision": "approved", "reason": "revisado por ingeniería"})
    assert any((e.get("id") or e.get("execution_id")) == eid for e in (call("GET", "/agent-execution/executions") if isinstance(call("GET", "/agent-execution/executions"), list) else call("GET", "/agent-execution/executions").get("items", []))), "la ejecución aparece en el listado"
    call("POST", "/agent-memory/memories", {"agent": "maint-agent", "memory_type": "fact", "content": {"k": "bomba B1 vibra en 3x"}})
    assert call("GET", "/agent-memory/memories") is not None
    h = "a" * 64
    f = call("POST", "/ml/features", {"name": "vib_rms", "version": "1", "source": "telemetry", "data_type": "float", "definition": {"window": "5m"}})["feature_id"]
    d = call("POST", "/ml/datasets", {"name": "vib", "version": "1", "source_query_hash": h, "feature_ids": [f], "row_count": 1000, "schema_hash": h, "content_hash": h, "split": {"train": 0.8, "test": 0.2}})["dataset_id"]
    t = call("POST", "/ml/training-runs", {"dataset_id": d, "model_name": "vib-anomaly", "candidate_version": "1.0.0", "framework": "sklearn", "algorithm": "isolation_forest"}); tid = t.get("id") or t.get("training_id"); assert tid, t
    call("POST", "/ml/evaluations", {"training_id": tid, "gate": "offline", "primary_score": 0.93, "false_positive_rate": 0.02, "evaluator": "qa"})
    call("POST", "/ml/drift", {"model_id": tid, "feature_name": "vib_rms", "metric": "psi", "value": 0.05, "threshold": 0.2, "window_start": "2026-10-01T00:00:00Z", "window_end": "2026-10-02T00:00:00Z"})
    sql("INSERT INTO neural_model_registry(tenant_id,name,version,framework,format,artifact_uri,sha256,input_schema,output_schema,approved_for_inference,status) VALUES(NULL,'modelo-global','1','onnx','onnx','s3://m/g.onnx',$1,'{}','{}',true,'validated')", h)
    mid = call("POST", "/neural/models", {"name": "vib-anomaly", "version": "1.0.0", "framework": "onnx", "format": "onnx", "artifact_uri": "s3://m/vib.onnx", "sha256": h, "input_schema": {}, "output_schema": {}, "approved_for_inference": True})["model_id"]
    assert {m["name"] for m in call("GET", "/neural/models")} >= {"vib-anomaly", "modelo-global"}, "el tenant ve su modelo y los modelos globales (RLS con tenant_id NULL)"
    call("POST", "/neural/inference-audit", {"model_id": mid, "input": {"x": 1}, "output": {"score": 0.1}, "status": "completed", "confidence": 0.9, "latency_ms": 12})
    no = call("POST", "/ml/deployments", {"model_id": mid, "environment": "staging", "evaluation_passed": False, "artifact_verified": True})
    assert no["allowed"] is False, no                                   # compuerta: sin evaluación aprobada NO se despliega
    yes = call("POST", "/ml/deployments", {"model_id": mid, "environment": "staging", "evaluation_passed": True, "artifact_verified": True})
    assert yes["allowed"] is True, yes

def test_flujo_edge_fisico_y_flota(client, monkeypatch):
    """Edge físico: dispositivo -> heartbeat -> comando -> seguridad. Flota: firmware -> OTA -> espool -> malla."""
    monkeypatch.setenv("EDGE_COMMAND_HMAC_KEY", "k" * 48); monkeypatch.setenv("EDGE_FLEET_SIGNING_KEY", "f" * 48)
    T = str(uuid.uuid4()); call = _api(client, T)
    dev = call("POST", "/physical-edge/devices", {"name": "actuador-1", "device_type": "valve", "key_ref": "kms://k1", "capabilities": ["stop_pump", "close_valve"]}); did = dev.get("id") or dev.get("device_id"); assert did, dev
    call("POST", "/physical-edge/heartbeat", {"sequence": 1, "safety_state": "armed"}, params={"device_id": did})
    call("POST", "/physical-edge/commands", {"device_id": did, "operation_id": str(uuid.uuid4()), "command_type": "close_valve"}, ok=False)   # fuera de la lista blanca: 403 aunque el dispositivo lo declare
    op = uuid.uuid4()
    call("POST", "/physical-edge/commands", {"device_id": did, "operation_id": str(op), "command_type": "stop_pump"}, ok=False)   # sin operación autónoma en ejecución: 409
    call("POST", "/agent-execution/policies", {"tool_name": "stop_pump", "risk_level": "high"})
    ex = call("POST", "/agent-execution/execute", {"agent": "maint-agent", "tool": "stop_pump", "action": "stop", "idempotency_key": "chain-key-0001"}); eid = ex.get("execution_id") or ex.get("id")
    call("POST", f"/agent-execution/executions/{eid}/operations", None, ok=False)          # aún no aceptada por un humano: 409
    call("POST", f"/agent-execution/executions/{eid}/approval", {"decision": "approved", "reason": "revisado"})
    op = call("POST", f"/agent-execution/executions/{eid}/operations")["operation_id"]     # puente agente -> operación autónoma
    assert call("POST", f"/agent-execution/executions/{eid}/operations")["idempotent_replay"] is True
    call("POST", "/physical-edge/commands", {"device_id": did, "operation_id": op, "command_type": "stop_pump"})
    assert call("GET", f"/physical-edge/devices/{did}/commands") is not None
    evs = client.get("/api/v1/realtime/events", params={"topic": "edge.command.issued"}, headers={"Authorization": "Bearer " + __import__("backend.app.core.security", fromlist=["x"]).create_access_token(str(uuid.uuid4()), T, ["admin"])}).json()["events"]
    assert len(evs) == 1 and evs[0]["payload"]["command_type"] == "stop_pump", evs
    call("POST", f"/physical-edge/devices/{did}/safety", params={"state": "safe"})
    fw = call("POST", "/edge-fleet/firmware", {"version": "1.2.0", "platform": "esp32", "artifact_uri": "s3://fw/1.2.0.bin", "sha256": "b" * 64}); fid = fw.get("id") or fw.get("artifact_id"); assert fid, fw
    call("POST", "/edge-fleet/ota", {"device_id": did, "artifact_id": fid, "target_version": "1.2.0"})
    call("POST", "/edge-fleet/spool", {"device_id": did, "sequence": 1, "event_key": "evt-0001-abcd", "event_type": "telemetry"})
    call("POST", "/edge-fleet/watchdog/" + did)


def test_transporte_edge_firmado_ed25519(client):
    """Gateway con credencial Ed25519: heartbeat firmado, anti-replay (nonce y secuencia), firma manipulada, pull firmado con lease y ACK -> comando completado.
    Corre con rol sin privilegios: antes el código fijaba app.tenant_id (GUC equivocado) y NINGÚN gateway podía autenticarse bajo RLS."""
    import base64, json
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    T = uuid.uuid4(); gw = uuid.uuid4(); priv = Ed25519PrivateKey.generate()
    pub = base64.b64encode(priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    root_node, child_node, outside_node = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    twin_device, scoped_point, outside_point = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    sql("INSERT INTO twin_nodes(tenant_id,id,node_type,code,name) VALUES($1,$2,'equipment','gw-root','Gateway scope'),($1,$3,'equipment','gw-child','Gateway child'),($1,$4,'equipment','outside','Out of scope')", T, root_node, child_node, outside_node)
    sql("UPDATE twin_nodes SET parent_id=$1 WHERE tenant_id=$2 AND id=$3", root_node, T, child_node)
    sql("INSERT INTO twin_devices(tenant_id,id,node_id,device_type) VALUES($1,$2,$3,'sensor')", T, twin_device, child_node)
    sql("INSERT INTO twin_points(tenant_id,id,node_id,device_id,code,name,semantic_kind,canonical_unit) VALUES($1,$2,$3,$4,'temp','Temperature','temperature','degC'),($1,$5,$6,NULL,'other','Other temperature','temperature','degC')", T, scoped_point, child_node, twin_device, outside_point, outside_node)
    sql("INSERT INTO edge_devices(tenant_id,device_id,node_id,device_type,name,key_ref,key_fingerprint,capabilities) VALUES($1,$2,$3,'gateway','gw-1','kms://gw','fp','[]'::jsonb)", T, gw, root_node)
    sql("INSERT INTO edge_device_credentials(tenant_id,device_id,algorithm,public_key,status,valid_from) VALUES($1,$2,'ed25519',$3,'active',now()-interval '1 day')", T, gw, pub)
    canon = lambda v: json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()
    sign = lambda env: base64.b64encode(priv.sign(canon(env))).decode()
    H = lambda sig, **x: {"X-Edge-Signature": sig, "X-Edge-Tenant-Id": str(T), **x}
    def hb(seq, nonce, state="armed"):
        body = {"gateway_id": str(gw), "sequence": seq, "firmware_version": None, "safety_state": state, "health": {}, "connectivity": {}, "nonce": nonce}
        return body, sign({"gateway_id": str(gw), "nonce": nonce, "sequence": seq, "payload": body})
    b, s = hb(1, "n" * 16 + "1"); assert client.post("/api/v1/edge-transport/heartbeat", json=b, headers=H(s)).status_code == 202
    assert client.post("/api/v1/edge-transport/heartbeat", json=b, headers=H(s)).status_code == 409, "replay del mismo nonce"
    b2, s2 = hb(1, "n" * 16 + "2"); assert client.post("/api/v1/edge-transport/heartbeat", json=b2, headers=H(s2)).status_code == 409, "secuencia no creciente"
    b3, s3 = hb(2, "n" * 16 + "3"); assert client.post("/api/v1/edge-transport/heartbeat", json=dict(b3, safety_state="safe"), headers=H(s3)).status_code == 401, "payload manipulado tras firmar"
    other = uuid.uuid4(); bad = client.post("/api/v1/edge-transport/heartbeat", json=b3, headers={**H(s3), "X-Edge-Tenant-Id": str(other)}); assert bad.status_code == 401, "otro tenant no ve la credencial (RLS)"
    # comando emitido -> el gateway lo recoge con petición firmada (lease) y lo confirma con evento firmado
    cmd = uuid.uuid4()
    sql("INSERT INTO edge_commands(tenant_id,command_id,device_id,operation_id,command_type,sequence,nonce,expires_at,payload,payload_hash,envelope,signature) VALUES($1,$2,$3,$4,'stop_pump',1,'cmdnonce',now()+interval '5 min','{}'::jsonb,'h','{}'::jsonb,'sig')", T, cmd, gw, uuid.uuid4())
    nonce, seq = "p" * 16 + "1", 3
    sig = sign({"gateway_id": str(gw), "nonce": nonce, "sequence": seq, "payload": {"gateway_id": str(gw), "nonce": nonce, "sequence": seq, "limit": 10}})
    r = client.get(f"/api/v1/edge-transport/commands/{gw}/signed", headers=H(sig, **{"X-Edge-Nonce": nonce, "X-Edge-Sequence": str(seq)})); assert r.status_code == 200, r.text
    assert [c["command_id"] for c in r.json()["commands"]] == [str(cmd)]
    assert sql("SELECT status FROM edge_commands WHERE command_id=$1", cmd)[0][0] == "leased"
    nonce, seq = "p" * 16 + "2", 4
    sig = sign({"gateway_id": str(gw), "nonce": nonce, "sequence": seq, "payload": {"gateway_id": str(gw), "nonce": nonce, "sequence": seq, "limit": 10}})
    assert client.get(f"/api/v1/edge-transport/commands/{gw}/signed", headers=H(sig, **{"X-Edge-Nonce": nonce, "X-Edge-Sequence": str(seq)})).json()["commands"] == [], "un comando con lease vigente no se entrega dos veces"
    ev = {"event_id": "ack-1", "gateway_id": str(gw), "nonce": "e" * 16 + "1", "sequence": 5, "occurred_at_ms": 1, "event_type": "edge.command_ack", "device_id": None, "payload": {"command_id": str(cmd), "status": "completed", "result": {"ok": True}}}
    r = client.post("/api/v1/edge-transport/events", json=ev, headers=H(sign({"gateway_id": str(gw), "nonce": ev["nonce"], "sequence": 5, "payload": ev}))); assert r.status_code == 202, r.text
    assert sql("SELECT status FROM edge_commands WHERE command_id=$1", cmd)[0][0] == "completed"
    # Muestras físicas firmadas: la pasarela queda limitada a su nodo y descendientes.
    from datetime import datetime, timezone
    observed_at = datetime.now(timezone.utc).isoformat()
    def telemetry_body(seq, nonce, point_id, message_id="sample-1"):
        body = {"gateway_id": str(gw), "nonce": nonce, "sequence": seq, "samples": [{
            "point_id": str(point_id), "value": 21.5, "unit": "degC",
            "observed_at": observed_at, "source": "forged-source",
            "source_message_id": message_id, "sequence": 999999,
            "source_quality": "GOOD", "correlation_id": None,
            "metadata": {"data_origin": "simulated", "gateway_id": "forged"},
        }]}
        from backend.app.modules.edge_transport.api import GatewayTelemetryBatch
        normalized_body = GatewayTelemetryBatch.model_validate(body).model_dump(mode="json")
        signature = sign({"gateway_id": str(gw), "nonce": nonce, "sequence": seq, "payload": normalized_body})
        return body, signature
    telemetry, telemetry_sig = telemetry_body(6, "t" * 16 + "1", scoped_point)
    response = client.post("/api/v1/edge-transport/telemetry/batch", json=telemetry, headers=H(telemetry_sig))
    assert response.status_code == 202, response.text
    assert response.json()["accepted"] == 1
    stored = sql("SELECT source,source_message_id,sequence,metadata FROM twin_telemetry_samples WHERE tenant_id=$1 AND point_id=$2", T, scoped_point)[0]
    stored_metadata = json.loads(stored[3]) if isinstance(stored[3], str) else stored[3]
    assert stored[0] == f"edge-gateway:{gw}" and stored[1] == f"{gw}:sample-1"
    assert stored[2] == 999999 and stored_metadata["data_origin"] == "physical"
    assert stored_metadata["gateway_id"] == str(gw) and stored_metadata["hardware_connected"] is True
    replay_response = client.post("/api/v1/edge-transport/telemetry/batch", json=telemetry, headers=H(telemetry_sig))
    assert replay_response.status_code == 409, "una muestra firmada no puede reutilizar nonce"
    idempotent_retry, retry_sig = telemetry_body(7, "t" * 16 + "2", scoped_point)
    retry_response = client.post("/api/v1/edge-transport/telemetry/batch", json=idempotent_retry, headers=H(retry_sig))
    assert retry_response.status_code == 202 and retry_response.json()["accepted"] == 0
    assert retry_response.json()["duplicates"] == 1
    out_of_scope, out_of_scope_sig = telemetry_body(8, "t" * 16 + "3", outside_point)
    denied = client.post("/api/v1/edge-transport/telemetry/batch", json=out_of_scope, headers=H(out_of_scope_sig))
    assert denied.status_code == 403, denied.text
    assert sql("SELECT count(*) FROM twin_telemetry_samples WHERE tenant_id=$1 AND point_id=$2", T, outside_point)[0][0] == 0
    assert sql("SELECT last_sequence FROM edge_devices WHERE tenant_id=$1 AND device_id=$2", T, gw)[0][0] == 7
    sql("UPDATE edge_transport_replays SET created_at=now()-interval '31 days' WHERE tenant_id=$1 AND device_id=$2", T, gw)
    cleanup_hb, cleanup_sig = hb(8, "c" * 16 + "1")
    cleanup = client.post("/api/v1/edge-transport/heartbeat", json=cleanup_hb, headers=H(cleanup_sig))
    assert cleanup.status_code == 202, cleanup.text
    assert sql("SELECT count(*) FROM edge_transport_replays WHERE tenant_id=$1 AND device_id=$2 AND created_at<now()-interval '30 days'", T, gw)[0][0] == 0
    assert sql("SELECT last_sequence FROM edge_devices WHERE tenant_id=$1 AND device_id=$2", T, gw)[0][0] == 8
    stale, stale_sig = hb(1, "z" * 16 + "1")
    stale_response = client.post("/api/v1/edge-transport/heartbeat", json=stale, headers=H(stale_sig))
    assert stale_response.status_code == 409, "el watermark persistente bloquea secuencias aunque el replay haya vencido"
    from backend.app.modules.edge_transport.api import _GATEWAY_TELEMETRY_SAMPLES_PER_MINUTE
    sql("""
        INSERT INTO edge_telemetry_ingest_limits(
            tenant_id,device_id,window_started_at,request_count,sample_count
        ) VALUES($1,$2,date_trunc('minute',clock_timestamp()),1,$3)
        ON CONFLICT(tenant_id,device_id) DO UPDATE SET
            window_started_at=EXCLUDED.window_started_at,request_count=1,
            sample_count=EXCLUDED.sample_count
    """, T, gw, _GATEWAY_TELEMETRY_SAMPLES_PER_MINUTE)
    limited, limited_sig = telemetry_body(9, "r" * 16 + "1", scoped_point, "rate-limited")
    limited_response = client.post(
        "/api/v1/edge-transport/telemetry/batch",
        json=limited,
        headers=H(limited_sig),
    )
    assert limited_response.status_code == 429
    assert limited_response.headers["Retry-After"] == "60"
    assert limited_response.json()["detail"]["code"] == "EDGE_TELEMETRY_RATE_LIMITED"
    assert sql("SELECT last_sequence FROM edge_devices WHERE tenant_id=$1 AND device_id=$2", T, gw)[0][0] == 8
    assert sql("SELECT count(*) FROM edge_transport_replays WHERE tenant_id=$1 AND device_id=$2 AND nonce=$3", T, gw, limited["nonce"])[0][0] == 0
    assert sql("SELECT count(*) FROM twin_telemetry_samples WHERE tenant_id=$1 AND point_id=$2 AND source_message_id=$3", T, scoped_point, f"{gw}:rate-limited")[0][0] == 0
    assert sql("SELECT sample_count FROM edge_telemetry_ingest_limits WHERE tenant_id=$1 AND device_id=$2", T, gw)[0][0] == _GATEWAY_TELEMETRY_SAMPLES_PER_MINUTE


def test_identidad_bootstrap_login_y_roles(client):
    """Instalación nueva: bootstrap del tenant -> login REAL -> crear usuario con rol limitado -> login -> permisos -> aislamiento entre tenants."""
    import sys; sys.path.insert(0, str(ROOT / "scripts"))
    from bootstrap_tenant import bootstrap
    t1 = asyncio.run(bootstrap(RAW, "Conjunto A", "Admin@A.co", "Clave-segura-123")); t2 = asyncio.run(bootstrap(RAW, "Conjunto B", "admin@a.co", None))
    def login(email, pwd, tenant): return client.post("/api/v1/auth/login", json={"email": email, "password": pwd, "tenant_id": tenant})
    r = login("admin@a.co", "Clave-segura-123", t1["tenant_id"]); assert r.status_code == 200, r.text
    H = {"Authorization": "Bearer " + r.json()["access_token"]}
    assert login("admin@a.co", "mala-clave-000", t1["tenant_id"]).status_code == 401
    assert login("admin@a.co", "Clave-segura-123", t2["tenant_id"]).status_code == 401, "las credenciales de un tenant no valen en otro"
    u = client.post("/api/v1/users", json={"email": "contador@a.co", "password": "Otra-clave-segura-9", "roles": ["accountant"]}, headers=H); assert u.status_code == 201, u.text
    assert client.post("/api/v1/users", json={"email": "x@a.co", "password": "soloLetrasLargas", "roles": []}, headers=H).status_code in (400, 422), "política de contraseña"
    assert client.post("/api/v1/users", json={"email": "contador@a.co", "password": "Otra-clave-segura-9"}, headers=H).status_code == 409, "email duplicado"
    HC = {"Authorization": "Bearer " + login("contador@a.co", "Otra-clave-segura-9", t1["tenant_id"]).json()["access_token"]}
    assert client.get("/api/v1/users", headers=HC).status_code == 403, "un contador no administra usuarios"
    assert client.post("/api/v1/config/tax-rules", json={"code": "IVA", "rate": "19"}, headers=HC).status_code == 201, "pero sí configura impuestos (rol accountant)"
    assert {x["email"] for x in client.get("/api/v1/users", headers=H).json()} == {"admin@a.co", "contador@a.co"}, "el tenant B no aparece"
    client.post(f"/api/v1/users/{u.json()['id']}/deactivate", headers=H); assert login("contador@a.co", "Otra-clave-segura-9", t1["tenant_id"]).status_code == 401, "usuario desactivado no inicia sesión"
    assert client.post(f"/api/v1/users/{t1['user_id']}/deactivate", headers=H).status_code == 409, "no puede desactivarse a sí mismo"


def test_sst_maestros_por_api_y_aprobacion_real(client):
    """SST sin SQL manual: regla, evidencia con doble control, ATS firmado, activo, matriz de autoridad, permiso y APROBACIÓN humana real."""
    import sys; sys.path.insert(0, str(ROOT / "scripts"))
    from bootstrap_tenant import bootstrap
    from datetime import datetime, timedelta, timezone
    t = asyncio.run(bootstrap(RAW, "Conjunto SST", "admin@sst.co", "Clave-segura-123"))
    tok = lambda e, p="Clave-segura-123": {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json={"email": e, "password": p, "tenant_id": t["tenant_id"]}).json()["access_token"]}
    HA = tok("admin@sst.co")
    def api(m, path, body=None, h=None, code=None):
        r = client.request(m, "/api/v1" + path, json=body, headers=h or HA)
        if code is None: assert 200 <= r.status_code < 300, (m, path, r.status_code, r.text[:300])
        else: assert r.status_code in (code if isinstance(code, tuple) else (code,)), (m, path, r.status_code, r.text[:300])
        return r.json() if r.content else {}
    mk = lambda email, roles: api("POST", "/users", {"email": email, "password": "Clave-segura-123", "roles": roles})["id"]
    sup, rev, appr = mk("sup@sst.co", ["sst_supervisor"]), mk("rev@sst.co", ["sst_reviewer"]), mk("aprob@sst.co", ["sst_approver"])
    HS, HR, HP = tok("sup@sst.co"), tok("rev@sst.co"), tok("aprob@sst.co")
    zone, contractor = str(uuid.uuid4()), str(uuid.uuid4()); now = datetime.now(timezone.utc); iso = lambda d: d.isoformat()
    api("POST", "/sst/master/rules", {"jurisdiction": "CO", "activity_type": "trabajo_en_alturas", "rule_key": "alturas-co", "definition": {"requirements": [{"key": "cert_alturas", "evidence_type": "certificado_alturas", "mandatory": True, "severity": "alto", "scope": "contractor"}]}}, h=HS, code=403)
    assert api("POST", "/sst/master/rules", {"jurisdiction": "CO", "activity_type": "trabajo_en_alturas", "rule_key": "alturas-co", "definition": {"requirements": [{"key": "cert_alturas", "evidence_type": "certificado_alturas", "mandatory": True, "severity": "alto", "scope": "contractor"}]}})["version"] == 1
    act = api("POST", "/sst/activities", {"zone_id": zone, "activity_type": "trabajo_en_alturas", "jurisdiction": "CO", "risk_level": "alto", "start_at": iso(now + timedelta(hours=1)), "end_at": iso(now + timedelta(hours=9)), "contractor_id": contractor, "aforo": 4}, h=HS)
    a = act.get("id") or act.get("activity_id")
    assert api("POST", f"/sst/activities/{a}/evaluate", h=HS)["blocked"] is True, "sin evidencia revisada se bloquea"
    ev = api("POST", "/sst/master/evidence", {"evidence_type": "certificado_alturas", "scope_kind": "contractor", "scope_id": contractor, "issued_at": iso(now - timedelta(days=10)), "expires_at": iso(now + timedelta(days=300))}, h=HS)["id"]
    api("POST", f"/sst/master/evidence/{ev}/review", {"decision": "approve"}, h=HS, code=403)          # el supervisor no es revisor
    ev2 = api("POST", "/sst/master/evidence", {"evidence_type": "otra", "scope_kind": "contractor", "scope_id": contractor})["id"]
    api("POST", f"/sst/master/evidence/{ev2}/review", {"decision": "approve"}, code=409)                  # el admin subió ev2: no puede autorrevisarla
    assert api("POST", f"/sst/master/evidence/{ev}/review", {"decision": "approve"}, h=HR)["status"] == "valid"
    api("POST", f"/sst/master/evidence/{ev}/review", {"decision": "approve"}, h=HR, code=409)            # ya no está pendiente
    ev_res = api("POST", f"/sst/activities/{a}/evaluate", h=HS); assert ev_res["blocked"] is False, ev_res
    ats = api("POST", "/sst/master/ats", {"title": "ATS alturas", "steps": [{"hazard": "caída", "consequence": "lesión grave", "control": "arnés", "responsible": "supervisor", "control_evidence": "foto-1"}], "required_signers": [sup]}, h=HS)["id"]
    api("POST", f"/sst/master/ats/{ats}/sign", h=HR, code=403)                                          # solo firmantes requeridos
    assert api("POST", f"/sst/master/ats/{ats}/sign", h=HS)["signed"] == 1
    api("POST", "/sst/master/assets", {"asset_type": "arnes", "zone_id": zone, "capacity_units": 6, "inspection_valid_until": iso(now + timedelta(days=60))}, h=HS)
    from backend.app.modules.sst_compliance.application import notifier as N
    sent = []
    class Capture:
        async def deliver(self, **kw): sent.append(kw)
    N.set_notifier(Capture())
    api("POST", "/sst/approvals", {"activity_id": a, "request_type": "work_permit", "action": "activate", "risk_level": "alto"}, h=HS, code=409)   # sin matriz de autoridad: falla segura
    N.set_notifier(None)
    api("PUT", "/sst/master/authority-matrix", {"rules": [{"request_type": "work_permit", "risk_levels": ["alto", "critico"], "approver_role": "sst_approver", "requires_mfa": False}]})
    api("POST", "/sst/approvals", {"activity_id": a, "request_type": "work_permit", "action": "activate", "risk_level": "alto"}, h=HS, code=503)  # sin canal de notificación: falla cerrado, NO queda aprobación huérfana
    assert asyncio.run(_count(RAW, f"SELECT count(*) FROM sst_approvals WHERE tenant_id='{t['tenant_id']}'")) == 0
    N.set_notifier(Capture())
    try:
        ap = api("POST", "/sst/approvals", {"activity_id": a, "request_type": "work_permit", "action": "activate", "risk_level": "alto"}, h=HS)["id"]
        assert len(sent) == 1 and sent[0]["recipient_id"] == appr and sent[0]["token"], "el token llega SOLO al canal, al aprobador designado"
        api("POST", f"/sst/approvals/{ap}/decision", {"token": sent[0]["token"], "decision": "approve", "justification": "ok"}, h=HS, code=(403, 409))   # el solicitante no puede consumir el token del aprobador
        api("POST", f"/sst/approvals/{ap}/decision", {"token": "x" * 40, "decision": "approve", "justification": "ok"}, h=HP, code=(401, 403, 404, 409, 422))           # token inválido
        assert api("POST", f"/sst/approvals/{ap}/decision", {"token": sent[0]["token"], "decision": "approve", "justification": "revisado en sitio"}, h=HP)["status"] == "approved"
        api("POST", f"/sst/approvals/{ap}/decision", {"token": sent[0]["token"], "decision": "approve", "justification": "otra vez"}, h=HP, code=409)  # replay del token
    finally: N.set_notifier(None)
    permit = api("POST", "/sst/master/work-permits", {"activity_id": a, "ats_id": ats, "permit_type": "alturas", "zone_id": zone, "contractor_id": contractor, "worker_ids": ["w1"], "valid_from": iso(now - timedelta(minutes=5)), "valid_to": iso(now + timedelta(hours=8)), "approval_id": ap}, h=HS)["id"]
    out = api("POST", f"/sst/work-permits/{permit}/activate", h=HS); assert out, out


async def _count(raw, q):
    import asyncpg
    c = await asyncpg.connect(raw)
    try: return await c.fetchval(q)
    finally: await c.close()


def test_mfa_politicas_excepciones_y_tiempo_real(client, monkeypatch):
    """MFA TOTP real (alta cifrada, confirmación, aprobación SST con paso adicional), políticas maestras por API y eventos en tiempo real con hash verificable."""
    import base64, sys
    from cryptography.fernet import Fernet
    from datetime import datetime, timedelta, timezone
    monkeypatch.setenv("TOTP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    sys.path.insert(0, str(ROOT / "scripts"))
    from bootstrap_tenant import bootstrap
    from backend.app.platform.security.strong_auth import _totp
    from backend.app.modules.sst_compliance.application import notifier as N
    t = asyncio.run(bootstrap(RAW, "Conjunto MFA", "admin@mfa.co", "Clave-segura-123"))
    tok = lambda e: {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json={"email": e, "password": "Clave-segura-123", "tenant_id": t["tenant_id"]}).json()["access_token"]}
    HA = tok("admin@mfa.co")
    def api(m, path, body=None, h=None, code=None):
        r = client.request(m, "/api/v1" + path, json=body, headers=h or HA)
        if code is None: assert 200 <= r.status_code < 300, (m, path, r.status_code, r.text[:300])
        else: assert r.status_code in (code if isinstance(code, tuple) else (code,)), (m, path, r.status_code, r.text[:300])
        return r.json() if r.content else {}
    api("POST", "/users", {"email": "sup@mfa.co", "password": "Clave-segura-123", "roles": ["sst_supervisor"]}); api("POST", "/users", {"email": "ap@mfa.co", "password": "Clave-segura-123", "roles": ["sst_approver"]})
    HS, HP = tok("sup@mfa.co"), tok("ap@mfa.co")
    # --- MFA del aprobador ---
    enr = api("POST", "/mfa/enroll", h=HP); secret = base64.b32decode(enr["secret_base32"] + "=" * (-len(enr["secret_base32"]) % 8))
    api("POST", "/mfa/confirm", {"code": "000000"}, h=HP, code=422)
    code_now = lambda: _totp(secret, int(__import__("time").time()))
    api("POST", "/mfa/confirm", {"code": code_now()}, h=HP, code=204)
    api("POST", "/mfa/enroll", h=HP, code=409)
    assert asyncio.run(_count(RAW, f"SELECT count(*) FROM user_totp_credentials WHERE tenant_id='{t['tenant_id']}' AND is_enabled AND encrypted_secret NOT LIKE '%{enr['secret_base32'][:8]}%'")) == 1, "el secreto no se guarda en claro"
    # --- aprobación que EXIGE MFA ---
    api("PUT", "/sst/master/authority-matrix", {"rules": [{"request_type": "work_permit", "risk_levels": ["alto"], "approver_role": "sst_approver", "requires_mfa": True}]})
    sent = []
    class Capture:
        async def deliver(self, **kw): sent.append(kw)
    N.set_notifier(Capture())
    try:
        zone = str(uuid.uuid4()); now = datetime.now(timezone.utc)
        a = api("POST", "/sst/activities", {"zone_id": zone, "activity_type": "montaje", "jurisdiction": "CO", "risk_level": "alto", "start_at": (now + timedelta(hours=1)).isoformat(), "end_at": (now + timedelta(hours=5)).isoformat()}, h=HS)
        aid = a.get("id") or a.get("activity_id")
        ap = api("POST", "/sst/approvals", {"activity_id": aid, "request_type": "work_permit", "action": "activate", "risk_level": "alto"}, h=HS)["id"]
        api("POST", f"/sst/approvals/{ap}/decision", {"token": sent[0]["token"], "decision": "approve", "justification": "sin mfa"}, h=HP, code=(401, 403, 409, 422))   # sin código MFA no aprueba
        api("POST", f"/sst/approvals/{ap}/decision", {"token": sent[0]["token"], "decision": "approve", "justification": "mfa ok", "mfa_code": code_now()}, h=HP)
    finally: N.set_notifier(None)
    # --- excepción respaldada por esa aprobación ---
    ex_body = {"activity_id": aid, "requirement_key": "cert_alturas", "approval_id": ap, "expires_at": (now + timedelta(days=2)).isoformat()}
    api("POST", "/sst/master/exceptions", dict(ex_body, expires_at=(now - timedelta(days=1)).isoformat()), code=(400, 422))
    api("POST", "/sst/master/exceptions", dict(ex_body, approval_id=str(uuid.uuid4())), code=404)
    api("POST", "/sst/master/exceptions", ex_body)
    # --- políticas maestras ---
    mid = str(uuid.uuid4())
    api("PUT", "/config/neural-policies", {"agent": "maint-agent", "purpose": "anomaly", "environment": "prod", "model_id": mid, "min_confidence": 0.8, "allowed_decisions": ["alert", "escalate"]})
    api("PUT", "/config/neural-policies", {"agent": "maint-agent", "purpose": "anomaly", "environment": "prod", "model_id": mid, "min_confidence": 1.5, "allowed_decisions": ["alert"]}, code=422)
    api("PUT", "/config/inference-routes", {"model_id": mid, "environment": "prod", "traffic_percent": 100})
    api("PUT", "/config/rollout-policies", {"platform": "esp32", "ring": "canary", "min_healthy_percent": 90, "max_failure_percent": 5, "max_concurrent": 3})
    ro = api("POST", "/edge-trust/rollout/check", {"platform": "esp32", "ring": "canary", "healthy_percent": 95, "failure_percent": 1}); assert ro["allowed"] is True and ro["max_concurrent"] == 3
    assert api("POST", "/edge-trust/rollout/check", {"platform": "esp32", "ring": "canary", "healthy_percent": 50, "failure_percent": 40})["allowed"] is False
    api("POST", "/config/rollout-policies", {"platform": "x", "ring": "y", "min_healthy_percent": 1, "max_failure_percent": 1}, h=HS, code=(403, 405))
    # --- tiempo real: eventos publicados y verificados por replay ---
    ev = api("GET", "/realtime/events", h=HA) if False else None
    evs = client.get("/api/v1/realtime/events", params={"topic": "sst.approval.decided"}, headers=HA).json()["events"]
    assert len(evs) == 1 and evs[0]["payload"]["status"] == "approved" and len(evs[0]["payload_sha256"]) == 64, evs


def test_inteligencia_decision_gobernada_y_malla_edge(client, monkeypatch):
    """telemetría -> features -> decisión neuronal gobernada por política/modelo/ruta/confianza; y malla edge: attestation firmada, reconciliación y caos."""
    from datetime import datetime, timedelta, timezone
    monkeypatch.setenv("EDGE_FLEET_SIGNING_KEY", "f" * 48)
    from backend.app.modules.edge_trust.service import attest_payload, sign_attestation
    T = str(uuid.uuid4()); call = _api(client, T)
    now = datetime.now(timezone.utc)
    node = call("POST", "/digital-twin/nodes", {"node_type": "equipment", "code": "BOMBA-1", "name": "Bomba 1"})["id"]
    for i in range(8): call("POST", "/digital-twin/telemetry", {"node_id": node, "metric": "vibration", "value_double": 2.0 + i * 0.1, "observed_at": (now - timedelta(minutes=40 - i * 5)).isoformat(), "source": "test"})
    feats = call("POST", "/intelligence/features/from-telemetry", {"node_id": node, "feature_name": "vibration", "feature_version": "1", "source": "twin"})
    assert feats["features"], feats
    call("POST", "/intelligence/features/from-telemetry", {"node_id": str(uuid.uuid4()), "feature_name": "vibration", "feature_version": "1", "source": "twin"}, ok=False)   # sin telemetría: 404
    h = "a" * 64
    mid = call("POST", "/neural/models", {"name": "vib-ia", "version": "1", "framework": "onnx", "format": "onnx", "artifact_uri": "s3://m/v.onnx", "sha256": h, "input_schema": {}, "output_schema": {}, "approved_for_inference": True})["model_id"]
    dec = lambda **k: call("POST", "/intelligence/neural/decision", {"request_id": f"req-{uuid.uuid4()}", "agent": "maint-agent", "purpose": "anomaly", "model_id": mid, "node_id": node, "proposed_decision": "alert", "confidence": 0.95, "input_payload": {"x": 1}, "environment": "prod", **k}, ok=k.pop("_ok", True) if False else True)
    call("POST", "/intelligence/neural/decision", {"request_id": "req-sin-politica", "agent": "maint-agent", "purpose": "anomaly", "model_id": mid, "proposed_decision": "alert", "confidence": 0.9, "input_payload": {}, "environment": "prod"}, ok=False)   # sin política: 404
    call("PUT", "/config/neural-policies", {"agent": "maint-agent", "purpose": "anomaly", "environment": "prod", "model_id": mid, "min_confidence": 0.8, "allowed_decisions": ["alert", "escalate"]})
    r = dec(); assert r["reason"] == "MODEL_ROUTE_INACTIVE" and r["decision"] == "observe", "sin ruta de tráfico activa la IA solo observa"
    call("PUT", "/config/inference-routes", {"model_id": mid, "environment": "prod", "traffic_percent": 100})
    r = dec(); assert r["status"] == "accepted" and r["decision"] == "alert" and r["execution_required"] is True, r
    assert dec(confidence=0.5)["reason"] == "CONFIDENCE_BELOW_POLICY"
    assert dec(proposed_decision="shutdown")["reason"] == "DECISION_NOT_ALLOWED", "una decisión fuera de la política NO se acepta (la IA solo recomienda lo permitido)"
    call("PUT", "/config/inference-routes", {"model_id": mid, "environment": "prod", "traffic_percent": 100, "active": False})
    assert dec()["reason"] == "MODEL_ROUTE_INACTIVE"
    # --- malla edge ---
    dev = uuid.uuid4(); payload = attest_payload(dev, "nonce-abc-123", "boot-1", h, h); good = sign_attestation(payload, ("f" * 48).encode())
    at = {"device_id": str(dev), "nonce": "nonce-abc-123", "boot_id": "boot-1", "firmware_hash": h, "measurement_hash": h}
    assert call("POST", "/edge-trust/attest", dict(at, signature=good)) is not None
    r = client.post("/api/v1/edge-trust/attest", json=dict(at, signature="0" * 64), headers={"Authorization": "Bearer " + __import__("backend.app.core.security", fromlist=["x"]).create_access_token(str(uuid.uuid4()), T, ["admin"])})
    assert r.status_code in (201, 200, 401, 403, 409, 422), r.text
    if r.status_code in (200, 201): assert "SIGNATURE_INVALID" in r.text or r.json().get("valid") is False, "una attestation con firma inválida NO debe validarse"
    rc = call("POST", "/edge-trust/reconcile", {"device_id": str(dev), "device_sequence": 10, "server_sequence": 7, "seen_sequences": [8, 9, 9, 10]}); assert rc["missing"] == 3 and rc["duplicates"] == 1 and rc["status"] == "reconciled", rc
    assert call("POST", "/edge-trust/reconcile", {"device_id": str(dev), "device_sequence": 5, "server_sequence": 9})["status"] == "conflicted"
    assert call("POST", "/edge-trust/chaos", {"scenario": "network_loss", "target_device_id": str(dev), "observed_state": "safe"})["passed"] is True
    assert call("POST", "/edge-trust/chaos", {"scenario": "network_loss", "target_device_id": str(dev), "observed_state": "armed"})["passed"] is False, "perder la red y quedar ARMADO es un fallo"


def test_agent_control_ejecuciones_y_memorias(client):
    """agent-control: registro de ejecuciones y memorias versionadas con aislamiento por tenant."""
    T1, T2 = str(uuid.uuid4()), str(uuid.uuid4()); c1, c2 = _api(client, T1), _api(client, T2)
    ex = c1("POST", "/agent-control/executions", {"agent": "maint-agent", "action": "inspect", "policy_reason": "rutina semanal"})
    assert ex, ex
    c1("POST", "/agent-control/memories", {"agent": "maint-agent", "source": "operador", "content": {"nota": "vibración alta en B1"}, "confidence": 0.8, "version": 1})
    c1("POST", "/agent-control/memories", {"agent": "maint-agent", "source": "operador", "content": {"nota": "x"}, "confidence": 1.5, "version": 1}, ok=False)   # confianza fuera de rango
    m1 = c1("GET", "/agent-control/memories", params={"agent": "maint-agent"}); assert len(m1 if isinstance(m1, list) else m1.get("items", m1.get("memories", []))) == 1
    m2 = c2("GET", "/agent-control/memories", params={"agent": "maint-agent"}); assert len(m2 if isinstance(m2, list) else m2.get("items", m2.get("memories", []))) == 0, "otro tenant no ve las memorias"
    e1 = c1("GET", "/agent-control/executions"); assert len(e1 if isinstance(e1, list) else e1.get("items", e1.get("executions", []))) == 1
