from datetime import datetime, timedelta, timezone
from backend.app.modules.sst_compliance.domain import approvals as A
from backend.app.modules.sst_compliance.domain.authority import AuthorityError, resolve
from ._util import raises

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
MATRIX = {"mfa_amount_threshold": 10_000_000, "rules": [
    {"request_type": "work_permit", "risk_levels": ["alto", "critico"], "approver_role": "SST_MANAGER"},
    {"request_type": "purchase", "risk_levels": ["bajo", "medio", "alto"], "min_amount": 0, "max_amount": 5_000_000, "approver_role": "BUDGET"},
    {"request_type": "purchase", "risk_levels": ["bajo", "medio", "alto"], "min_amount": 5_000_000, "approver_role": "DIRECTOR"},
]}
USERS = [{"id": "u2", "roles": ["SST_MANAGER", "BUDGET"]}, {"id": "u1", "roles": ["SST_MANAGER"]},
         {"id": "u3", "roles": ["DIRECTOR"]}, {"id": "ux", "roles": ["SST_MANAGER"], "active": False}]


def test_permiso_sin_cuantia_no_revienta_y_es_determinista():
    r = resolve(MATRIX, request_type="work_permit", risk_level="alto", requester_id="req", users=USERS)
    assert r.primary_id == "u1" and r.backup_id == "u2" and not r.requires_mfa


def test_riesgo_critico_exige_mfa():
    assert resolve(MATRIX, request_type="work_permit", risk_level="critico", requester_id="req", users=USERS).requires_mfa


def test_sin_autoaprobacion():
    r = resolve(MATRIX, request_type="work_permit", risk_level="alto", requester_id="u1", users=USERS)
    assert r.primary_id == "u2" and r.backup_id is None


def test_limite_de_cuantia_semiabierto():
    assert resolve(MATRIX, request_type="purchase", risk_level="bajo", requester_id="r", users=USERS, amount=4_999_999).approver_role == "BUDGET"
    assert resolve(MATRIX, request_type="purchase", risk_level="bajo", requester_id="r", users=USERS, amount=5_000_000).approver_role == "DIRECTOR"


def test_compra_sin_monto_falla_segura():
    with raises(AuthorityError):
        resolve(MATRIX, request_type="purchase", risk_level="bajo", requester_id="r", users=USERS)


def test_sin_matriz_o_sin_candidato_falla():
    with raises(AuthorityError):
        resolve(None, request_type="work_permit", risk_level="alto", requester_id="r", users=USERS)
    with raises(AuthorityError):
        resolve(MATRIX, request_type="work_permit", risk_level="alto", requester_id="r", users=[{"id": "r", "roles": ["SST_MANAGER"]}])


def test_matriz_ambigua_falla():
    m = {"rules": MATRIX["rules"][:1] * 2}
    with raises(AuthorityError):
        resolve(m, request_type="work_permit", risk_level="alto", requester_id="r", users=USERS)


def mk(**kw):
    d = dict(id="ap1", activity_id="a1", action="approve_permit", requester_id="req", primary_id="u1", backup_id="u2",
             requires_mfa=False, expires_at=NOW + timedelta(hours=2))
    d.update(kw)
    return A.Approval(**d)


def test_token_un_solo_uso_y_hash():
    ap = mk()
    raw, rec = A.issue_token(ap, "u1", NOW)
    assert raw not in rec.token_hash and len(rec.token_hash) == 64
    A.validate_token(rec, raw, approval=ap, action="approve_permit", actor_id="u1", now=NOW, mfa_verified=False)
    import dataclasses
    used = dataclasses.replace(rec, used_at=NOW)
    with raises(A.ApprovalError, "TOKEN_REPLAY"):
        A.validate_token(used, raw, approval=ap, action="approve_permit", actor_id="u1", now=NOW, mfa_verified=False)


def test_token_vencido_accion_destinatario_version():
    import dataclasses
    ap = mk()
    raw, rec = A.issue_token(ap, "u1", NOW)
    kw = dict(approval=ap, action="approve_permit", actor_id="u1", mfa_verified=False)
    with raises(A.ApprovalError, "TOKEN_EXPIRED"):
        A.validate_token(rec, raw, now=NOW + timedelta(minutes=16), **kw)
    with raises(A.ApprovalError, "TOKEN_ACTION_MISMATCH"):
        A.validate_token(rec, raw, now=NOW, **{**kw, "action": "reject"})
    with raises(A.ApprovalError, "TOKEN_RECIPIENT_MISMATCH"):
        A.validate_token(rec, raw, now=NOW, **{**kw, "actor_id": "u2"})
    with raises(A.ApprovalError, "TOKEN_STALE_VERSION"):
        A.validate_token(rec, raw, now=NOW, **{**kw, "approval": dataclasses.replace(ap, version=2)})
    with raises(A.ApprovalError, "TOKEN_INVALID"):
        A.validate_token(rec, "otro-token", now=NOW, **kw)


def test_token_no_puede_vivir_mas_que_la_aprobacion():
    ap = mk(expires_at=NOW + timedelta(minutes=3))
    _, rec = A.issue_token(ap, "u1", NOW)
    assert rec.expires_at == ap.expires_at


def test_mfa_obligatorio():
    ap = mk(requires_mfa=True)
    with raises(A.ApprovalError, "MFA_REQUIRED"):
        A.decide(ap, actor_id="u1", decision="approve", justification=None, now=NOW, mfa_verified=False)
    assert A.decide(ap, actor_id="u1", decision="approve", justification=None, now=NOW, mfa_verified=True).grants_authorization


def test_decision_reglas():
    ap = mk()
    with raises(A.ApprovalError, "SELF_APPROVAL"):
        A.decide(ap, actor_id="req", decision="approve", justification=None, now=NOW, mfa_verified=True)
    with raises(A.ApprovalError, "NOT_AUTHORIZED_APPROVER"):
        A.decide(ap, actor_id="zz", decision="approve", justification=None, now=NOW, mfa_verified=True)
    with raises(A.ApprovalError, "JUSTIFICATION_REQUIRED"):
        A.decide(ap, actor_id="u1", decision="reject", justification=" ", now=NOW, mfa_verified=True)
    with raises(A.ApprovalError, "APPROVAL_EXPIRED"):
        A.decide(ap, actor_id="u1", decision="approve", justification=None, now=NOW + timedelta(hours=3), mfa_verified=True)


def test_silencio_nunca_aprueba():
    out = A.expire_if_due(mk(), NOW + timedelta(hours=3))
    assert out.status is A.ApprovalStatus.EXPIRED and not out.grants_authorization


def test_cambio_de_alcance_invalida():
    out = A.invalidate_on_scope_change(A.decide(mk(), actor_id="u1", decision="approve", justification=None, now=NOW, mfa_verified=True), changed={"zone"})
    assert out.status is A.ApprovalStatus.INVALIDATED and out.version == 2 and not out.grants_authorization


def test_conflicto_de_interes_excluye_aprobador():
    users = [{"id": "u1", "roles": ["SST_MANAGER"], "conflicts": ["req"]}, {"id": "u2", "roles": ["SST_MANAGER"]}]
    r = resolve(MATRIX, request_type="work_permit", risk_level="alto", requester_id="req", users=users)
    assert r.primary_id == "u2" and r.backup_id is None
