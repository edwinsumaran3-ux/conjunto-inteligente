import dataclasses, hashlib, hmac, json
from datetime import datetime, timedelta, timezone
from backend.app.modules.sst_compliance.domain import audit_chain as C
from backend.app.modules.sst_compliance.domain import coverage as V
from backend.app.modules.sst_compliance.domain import notifications as N
from backend.app.modules.sst_compliance.domain import work_permit as W
from ._util import raises

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
H = timedelta(hours=1)


# ---------- permiso / ATS ----------
def permit(**kw):
    d = dict(id="p1", activity_id="a1", ats_id="ats1", ats_version=1, permit_type="altura", zone_id="z1",
             contractor_id="c1", worker_ids=frozenset({"w1"}), valid_from=NOW, valid_to=NOW + 8 * H)
    d.update(kw)
    return W.WorkPermit(**d)


def ok_args(**kw):
    d = dict(now=NOW, approval_granted=True, evaluation_blocked=False, ats_missing=[])
    d.update(kw)
    return d


def test_ats_detecta_faltantes():
    miss = W.validate_ats([{"hazard": "caída"}], [], ["sup1"])
    assert any("control" in m for m in miss) and any("sup1" in m for m in miss)
    full = {k: "x" for k in W.STEP_FIELDS}
    assert W.validate_ats([full], [{"user_id": "sup1", "signed_at": "t"}], ["sup1"]) == []


def test_permiso_requiere_aprobacion_sin_bloqueos_y_ats():
    for bad, code in [(dict(approval_granted=False), "APPROVAL_REQUIRED"), (dict(evaluation_blocked=True), "CRITICAL_BLOCKER"),
                      (dict(ats_missing=["x"]), "ATS_INCOMPLETE")]:
        with raises(W.PermitError, code):
            W.activate(permit(), **ok_args(**bad))
    assert W.activate(permit(), **ok_args()).status is W.PermitStatus.ACTIVE


def test_permiso_ventana_maxima_y_sin_personas():
    with raises(W.PermitError, "PERMIT_WINDOW"):
        W.activate(permit(valid_to=NOW + 30 * H), **ok_args())
    with raises(W.PermitError, "PERMIT_NO_WORKERS"):
        W.activate(permit(worker_ids=frozenset()), **ok_args())


def test_permiso_no_se_reutiliza_en_otra_zona_contratista_persona_actividad_o_dia():
    p = W.activate(permit(), **ok_args())
    base = dict(now=NOW + H, zone_id="z1", contractor_id="c1", worker_id="w1", activity_id="a1")
    assert p.authorizes(**base)
    for k, v in [("zone_id", "z2"), ("contractor_id", "c2"), ("worker_id", "w9"), ("activity_id", "a2")]:
        assert not p.authorizes(**{**base, k: v})
    assert not p.authorizes(**{**base, "now": NOW + 9 * H}) and p.effective_status(NOW + 9 * H) is W.PermitStatus.EXPIRED


def test_cambio_material_suspende_y_cierre_exige_inspeccion():
    p = W.activate(permit(), **ok_args())
    assert W.apply_change(p, {"zone"}).status is W.PermitStatus.SUSPENDED
    assert W.apply_change(p, {"foto"}).status is W.PermitStatus.ACTIVE
    with raises(W.PermitError, "INSPECTION_REQUIRED"):
        W.close(p, final_inspection_ok=False, open_critical_risks=0, unreconciled_resources=0)
    with raises(W.PermitError, "CLOSE_BLOCKED"):
        W.close(p, final_inspection_ok=True, open_critical_risks=1, unreconciled_resources=0)
    assert W.close(p, final_inspection_ok=True, open_critical_risks=0, unreconciled_resources=0).status is W.PermitStatus.CLOSED


# ---------- cobertura ----------
def asset(i, **kw):
    d = dict(id=i, asset_type="extintor", zone_id="z1", status="disponible", capacity_units=10,
             inspection_valid_until=NOW + 90 * 24 * H, expires_at=None)
    d.update(kw)
    return d


def cov(assets, req=20, asg=(), other=()):
    return V.compute_coverage(zone_id="z1", asset_type="extintor", required_units=req, start_at=NOW, end_at=NOW + 4 * H,
                              assets=assets, assignments=asg, other_reservations=other)


def test_cobertura_mide_capacidad_no_filas():
    r = cov([asset("a"), asset("b", capacity_units=5)])
    assert r.state is V.CoverageState.BRECHA and r.gap == 5 and r.available_units == 15


def test_cobertura_excluye_fuera_de_servicio_sin_inspeccion_y_desconocidos():
    r = cov([asset("a"), asset("b", status="fuera_servicio"), asset("c", inspection_valid_until=None),
             asset("d", status=None), asset("e", capacity_units=None)], req=10)
    assert r.state is V.CoverageState.CUBIERTA and r.counted == ("a",) and len(r.excluded) == 4


def test_cantidad_requerida_desconocida_no_se_inventa():
    r = cov([asset("a")], req=None)
    assert r.state is V.CoverageState.DESCONOCIDA and r.gap is None


def test_temporal_solo_cuenta_si_verificado_y_cubre_ventana():
    t = asset("t", zone_id="otra")
    prop = dict(asset_id="t", zone_id="z1", status="proposed", start_at=NOW - H, end_at=NOW + 9 * H)
    assert cov([t], req=10, asg=[prop]).state is V.CoverageState.BRECHA
    assert cov([t], req=10, asg=[{**prop, "status": "verified"}]).state is V.CoverageState.CUBIERTA
    assert cov([t], req=10, asg=[{**prop, "status": "verified", "end_at": NOW + H}]).state is V.CoverageState.BRECHA


def test_reservado_en_otra_zona_se_excluye():
    r = cov([asset("a")], req=10, other=[dict(asset_id="a", activity_zone="z9", start_at=NOW, end_at=NOW + H)])
    assert r.state is V.CoverageState.BRECHA


def test_ciclo_asignacion_temporal():
    a = V.propose(id="t1", activity_id="a1", asset_id="x", zone_id="z1", start_at=NOW, end_at=NOW + 8 * H, responsible_id="r", proposed_by="p")
    with raises(V.CoverageError, "ZONE_REQUIRED"):
        V.propose(id="t", activity_id="a", asset_id="x", zone_id="", start_at=NOW, end_at=NOW + H, responsible_id="r", proposed_by="p")
    with raises(V.CoverageError, "NOT_VERIFIED"):
        V.activate_assignment(a, NOW)
    with raises(V.CoverageError, "PHYSICAL_VERIFICATION_REQUIRED"):
        V.verify(a, verifier_id="v", inspection_id=None, physical_check_ok=True)
    with raises(V.CoverageError, "SELF_VERIFICATION"):
        V.verify(a, verifier_id="p", inspection_id="i", physical_check_ok=True)
    v = V.verify(a, verifier_id="v", inspection_id="i1", physical_check_ok=True)
    act = V.activate_assignment(v, NOW + H)
    with raises(V.CoverageError, "RETURN_INSPECTION_REQUIRED"):
        V.return_assignment(act, return_inspection_ok=False)
    assert V.return_assignment(act, return_inspection_ok=True).status == "returned"
    assert V.asset_state_after_recharge_return(inspected_ok=False) == "mantenimiento"


# ---------- cadena de auditoría ----------
def build(n=5):
    links, last = [], None
    for i in range(n):
        last = C.next_link(last, f"2026-11-01T12:00:0{i}+00:00", {"tenant_id": "t", "action": f"a{i}", "after": {"i": i}})
        links.append(last)
    return links


def test_cadena_valida_y_detecta_alteracion():
    L = build()
    assert C.verify(L).valid
    bad = list(L); bad[2] = dataclasses.replace(L[2], event={**L[2].event, "action": "FORJADO"})
    v = C.verify(bad)
    assert not v.valid and v.first_bad_seq == 3


def test_cadena_detecta_hueco_y_bifurcacion():
    L = build()
    assert C.verify(L[:2] + L[3:]).first_bad_seq == 4
    fork = C.next_link(L[1], "2026-11-01T12:00:09+00:00", {"tenant_id": "t", "action": "x"})
    assert not C.verify(L[:3] + [fork]).valid


def test_hash_es_determinista_con_una_sola_marca_de_tiempo():
    a = C.compute_hash("P", 1, "ts", {"action": "x", "after": {"b": 1, "a": 2}})
    b = C.compute_hash("P", 1, "ts", {"after": {"a": 2, "b": 1}, "action": "x"})
    assert a == b


# ---------- notificaciones / webhook ----------
def test_firma_meta():
    body, sec = b'{"x":1}', "s3cret"
    good = "sha256=" + hmac.new(sec.encode(), body, hashlib.sha256).hexdigest()
    N.verify_meta_signature(body, good, sec)
    for hdr, s in [(None, sec), ("sha256=00", sec), (good, None), ("md5=1", sec)]:
        with raises(N.WebhookError):
            N.verify_meta_signature(body, hdr, s)
    with raises(N.WebhookError):
        N.verify_meta_signature(b'{"x":2}', good, sec)


def test_handshake_suscripcion():
    assert N.verify_subscription("subscribe", "tok", "123", "tok") == "123"
    with raises(N.WebhookError):
        N.verify_subscription("subscribe", "mal", "123", "tok")
    with raises(N.WebhookError):
        N.verify_subscription("subscribe", "tok", "123", None)


def test_eventos_estado_y_replay():
    ts = int(NOW.timestamp())
    payload = {"entry": [{"changes": [{"value": {"statuses": [{"id": "m1", "status": "read", "timestamp": str(ts), "biz_opaque_callback_data": "ten1:att1"}, {"id": "bad"}]}}]}]}
    evs = N.extract_status_events(payload)
    assert len(evs) == 1 and evs[0].status == "read" and (evs[0].tenant_id, evs[0].attempt_id) == ("ten1", "att1")
    assert not N.is_replay(evs[0], set(), NOW)
    assert N.is_replay(evs[0], {evs[0].event_id}, NOW)
    assert N.is_replay(evs[0], set(), NOW + timedelta(days=2))


def test_reintento_regenera_token_cambia_canal_y_escala():
    kw = dict(channel="whatsapp", has_backup=True, approval_expired=False)
    d = N.next_step(attempts=2, last_attempt_at=NOW - timedelta(hours=1), now=NOW, **kw)
    assert d.action == "retry" and d.channel != "whatsapp" and d.regenerate_token
    d = N.next_step(attempts=1, last_attempt_at=NOW - timedelta(minutes=1), now=NOW, **kw)
    assert d.action == "retry" and d.at > NOW and not d.regenerate_token
    assert N.next_step(attempts=3, last_attempt_at=NOW, now=NOW, **kw).action == "escalate_backup"
    assert N.next_step(attempts=3, last_attempt_at=NOW, now=NOW, **{**kw, "has_backup": False}).action == "give_up"
    assert N.next_step(attempts=0, last_attempt_at=NOW, now=NOW, **{**kw, "approval_expired": True}).action == "give_up"


def test_cadena_detecta_enlace_roto_aunque_cada_hash_sea_valido():
    L = build(4)
    alt = C.next_link(L[1], "2026-11-01T12:00:59+00:00", {"tenant_id": "t", "action": "rama-alterna"})
    # alt es un eslabón autoconsistente (seq 3) pero L[3] fue construido sobre L[2], no sobre alt
    v = C.verify([L[0], L[1], alt, L[3]])
    assert not v.valid and v.first_bad_seq == 4 and "prev_hash" in v.reason
