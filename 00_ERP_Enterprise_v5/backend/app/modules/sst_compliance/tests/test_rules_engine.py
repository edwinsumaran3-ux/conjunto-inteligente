from datetime import datetime, timedelta, timezone
from backend.app.modules.sst_compliance.domain.rules_engine import ActivityContext, NoApplicableRules, RulesEngine
from backend.app.modules.sst_compliance.domain.states import RequirementStatus as S
from ._util import raises

T0 = datetime(2026, 11, 1, 15, 0, tzinfo=timezone.utc)  # 10:00 Bogotá
T1 = T0 + timedelta(hours=4)


def ctx(**kw):
    d = dict(activity_id="a1", activity_type="evento", jurisdiction="CO", risk_level="alto", zone_id="z1",
             start_at=T0, end_at=T1, aforo=200, requester_id="u-req")
    d.update(kw)
    return ActivityContext(**d)


def rule(reqs, **kw):
    r = dict(id="r1", rule_key="evento_base", version="1", jurisdiction="CO", activity_type="evento",
             effective_from=T0 - timedelta(days=30), expires_at=None, approved_by="u-sst",
             definition={"requirements": reqs})
    r.update(kw)
    return r


REQ = {"key": "extintor", "severity": "critico", "evidence_type": "insp_extintor", "scope": "zone"}


def ev(**kw):
    d = dict(id="e1", type="insp_extintor", scope_kind="zone", scope_id="z1", issued_at=T0 - timedelta(days=5),
             expires_at=T1 + timedelta(days=30), status="valid")
    d.update(kw)
    return d


def one(reqs, evidence, c=None, exceptions=()):
    return RulesEngine().evaluate(c or ctx(), [rule(reqs)], evidence, exceptions).results[0]


def test_sin_reglas_falla_segura():
    with raises(NoApplicableRules):
        RulesEngine().evaluate(ctx(), [], [])


def test_regla_sin_aprobador_se_ignora():
    with raises(NoApplicableRules):
        RulesEngine().evaluate(ctx(), [rule([REQ], approved_by=None)], [])


def test_sin_evidencia_pendiente_y_bloquea():
    r = one([REQ], [])
    assert r.status is S.PENDIENTE and r.blocks_start


def test_evidencia_de_otra_zona_no_cuenta():
    r = one([REQ], [ev(scope_id="z-otra")])
    assert r.status is S.PENDIENTE


def test_evidencia_vigente_cumple():
    r = one([REQ], [ev()])
    assert r.status is S.CUMPLE and not r.blocks_start


def test_vence_durante_la_actividad_es_vencido():
    r = one([REQ], [ev(expires_at=T0 + timedelta(hours=1))])
    assert r.status is S.VENCIDO


def test_sin_vigencia_declarada_es_desconocido():
    r = one([REQ], [ev(expires_at=None)])
    assert r.status is S.DESCONOCIDO and r.blocks_start


def test_max_age_days_suple_vencimiento():
    req = dict(REQ, max_age_days=365)
    assert one([req], [ev(expires_at=None)]).status is S.CUMPLE


def test_revision_obligatoria_en_revision_y_cumple():
    req = dict(REQ, requires_review=True)
    assert one([req], [ev()]).status is S.EN_REVISION
    assert one([req], [ev(reviewed_by="u-sst", reviewed_at=T0, uploaded_by="u-x")]).status is S.CUMPLE
    assert one([req], [ev(reviewed_by="u-x", reviewed_at=T0, uploaded_by="u-x")]).status is S.EN_REVISION


def test_evidencia_rechazada_no_cumple():
    assert one([REQ], [ev(status="rejected")]).status is S.NO_CUMPLE


def test_evidencia_revocada_ignorada():
    assert one([REQ], [ev(status="revoked")]).status is S.PENDIENTE


def test_condicion_aforo_no_aplica_y_desconocido():
    req = dict(REQ, condition={"aforo_min": 100})
    assert one([req], [], ctx(aforo=50)).status is S.NO_APLICA
    assert one([req], [], ctx(aforo=None)).status is S.DESCONOCIDO


def test_ventana_horaria_en_zona_de_la_organizacion():
    req = dict(REQ, condition={"time_window": {"from": 22, "to": 6}})
    assert one([req], [], ctx()).status is S.NO_APLICA  # 10:00 Bogotá fuera de 22-06
    night = T0.replace(hour=4)  # 23:00 Bogotá
    assert one([req], [], ctx(start_at=night, end_at=night + timedelta(hours=2))).status is S.PENDIENTE


def test_scope_contratista_sin_contratista_es_desconocido():
    req = dict(REQ, scope="contractor", evidence_type="arl")
    assert one([req], []).status is S.DESCONOCIDO


def test_excepcion_solo_si_la_norma_la_admite():
    x = [dict(requirement_key="extintor", approval_id="ap1", approved_by="u-dir")]
    assert one([REQ], [], exceptions=x).status is S.PENDIENTE
    assert one([dict(REQ, allows_exception=True)], [], exceptions=x).status is S.EXCEPCION


def test_excepcion_autoaprobada_se_ignora():
    x = [dict(requirement_key="extintor", approval_id="ap1", approved_by="u-req")]
    assert one([dict(REQ, allows_exception=True)], [], exceptions=x).status is S.PENDIENTE


def test_reevaluar_no_duplica_resultados():
    e = RulesEngine().evaluate(ctx(), [rule([REQ]), rule([REQ], id="r2", version="2",
                                                          effective_from=T0 - timedelta(days=1))], [ev()])
    assert len(e.results) == 1 and e.rules_used == (("evento_base", "2"),)


def test_bloqueo_critico_no_se_oculta_en_porcentaje():
    reqs = [REQ] + [dict(REQ, key=f"k{i}", severity="bajo", evidence_type=f"t{i}") for i in range(9)]
    evid = [ev(id=f"e{i}", type=f"t{i}") for i in range(9)]
    e = RulesEngine().evaluate(ctx(), [rule(reqs)], evid)
    assert e.blocked and len(e.critical_blockers) == 1 and e.counts()["cumple"] == 9


def test_fechas_sin_zona_horaria_rechazadas():
    with raises(ValueError):
        ctx(start_at=datetime(2026, 11, 1, 10))
