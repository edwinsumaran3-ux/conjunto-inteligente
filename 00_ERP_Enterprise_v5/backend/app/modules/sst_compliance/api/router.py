from __future__ import annotations
import os
from datetime import datetime
from uuid import UUID
from ..application.notifier import get_notifier
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session
from backend.app.db.session import get_session_factory
from sqlalchemy import text
from ..application.service import NotFound, SstService
from ..domain import approvals as AP
from ..domain import coverage as CV
from ..domain import notifications as NT
from ..domain import work_permit as WP
from ..domain.authority import AuthorityError
from ..domain.rules_engine import NoApplicableRules

router = APIRouter(prefix="/sst", tags=["sst-compliance"])
svc = SstService()


def _http(e: Exception) -> HTTPException:
    if isinstance(e, NotFound):
        return HTTPException(404, {"code": "NOT_FOUND", "detail": str(e)})
    if isinstance(e, NoApplicableRules):
        return HTTPException(409, {"code": "NO_RULES", "detail": str(e)})
    code = getattr(e, "code", e.__class__.__name__.upper())
    return HTTPException(409 if isinstance(e, (AP.ApprovalError, WP.PermitError, CV.CoverageError, AuthorityError)) else 400,
                         {"code": code, "detail": str(e)})


def _resp(e: Exception) -> JSONResponse:
    """Devuelve (no lanza) el error: get_tenant_session hace rollback ante excepciones y se perdería
    la auditoría del intento rechazado (token reutilizado, sin reglas, etc.). Con respuesta, se confirma."""
    h = _http(e)
    return JSONResponse(status_code=h.status_code, content=h.detail)


class ActivityIn(BaseModel):
    zone_id: UUID; activity_type: str = Field(min_length=2, max_length=80); jurisdiction: str = Field(min_length=2, max_length=40)
    risk_level: str = Field(pattern="^(bajo|medio|alto|critico)$"); start_at: datetime; end_at: datetime
    aforo: int | None = Field(None, ge=0); contractor_id: UUID | None = None; asset_id: UUID | None = None
    timezone: str = "America/Bogota"


class ApprovalIn(BaseModel):
    request_type: str; action: str; risk_level: str = Field(pattern="^(bajo|medio|alto|critico)$")
    activity_id: UUID | None = None; amount: float | None = Field(None, ge=0); ttl_hours: int = Field(24, ge=1, le=168)
    conditions: dict = {}


class DecisionIn(BaseModel):
    token: str = Field(min_length=20); decision: str = Field(pattern="^(approve|reject|request_changes)$")
    justification: str | None = None; mfa_code: str | None = Field(None, pattern="^[0-9]{6,8}$")


class AssignmentIn(BaseModel):
    activity_id: UUID; asset_id: UUID; zone_id: UUID; start_at: datetime; end_at: datetime; responsible_id: UUID


class VerifyIn(BaseModel):
    inspection_id: UUID | None = None; physical_check_ok: bool


@router.post("/activities", status_code=201)
async def create_activity(b: ActivityIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    try:
        return {"id": str(await svc.create_activity(s, UUID(a.tenant_id), UUID(a.user_id), b.model_dump(mode="python")))}
    except Exception as e:  # noqa: BLE001
        raise _http(e) from e


@router.post("/activities/{activity_id}/evaluate")
async def evaluate(activity_id: UUID, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    try:
        r = await svc.evaluate(s, UUID(a.tenant_id), UUID(a.user_id), activity_id)
    except (NotFound, NoApplicableRules) as e:
        return _resp(e)
    return {"blocked": r.blocked, "counts": r.counts(), "critical_blockers": [x.requirement_key for x in r.critical_blockers],
            "blockers": [{"key": x.requirement_key, "status": x.status.value, "reason": x.reason} for x in r.blockers]}


@router.get("/activities/{activity_id}/requirements")
async def requirements(activity_id: UUID, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    return {"items": await svc.requirements(s, UUID(a.tenant_id), activity_id)}


@router.post("/approvals", status_code=201)
async def create_approval(b: ApprovalIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    try:
        notifier = get_notifier()          # falla cerrado ANTES de crear nada si no hay canal
        apid, delivery = await svc.create_approval(s, UUID(a.tenant_id), UUID(a.user_id), b.model_dump(mode="python"))
    except HTTPException: raise
    except Exception as e:  # noqa: BLE001
        raise _http(e) from e
    try:
        await notifier.deliver(tenant_id=a.tenant_id, approval_id=str(apid), recipient_id=delivery["recipient_id"], token=delivery["token"], expires_at=None)
    except Exception as e:  # noqa: BLE001 - si no se pudo entregar, la transacción se revierte (la aprobación no queda huérfana)
        raise HTTPException(502, {"code": "APPROVAL_NOTIFICATION_FAILED", "detail": type(e).__name__}) from e
    # El token en claro NO se devuelve al solicitante: lo recibe el aprobador por el canal de notificación.
    return {"id": str(apid), "status": "pending"}


@router.post("/approvals/{approval_id}/decision")
async def decision(approval_id: UUID, b: DecisionIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    try:
        st = await svc.decide(s, UUID(a.tenant_id), UUID(a.user_id), approval_id, token=b.token, decision=b.decision,
                              justification=b.justification, mfa_code=b.mfa_code)
    except (AP.ApprovalError, NotFound) as e:
        return _resp(e)
    from backend.app.platform.realtime.service import publish
    await publish(s, tenant_id=UUID(a.tenant_id), topic="sst.approval.decided", payload={"approval_id": str(approval_id), "status": st}, correlation_id=str(approval_id))
    return {"id": str(approval_id), "status": st}


@router.post("/approvals/expire-due")
async def expire_due(a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    if "SST_ADMIN" not in a.roles and "ADMIN" not in a.roles:
        raise HTTPException(403, {"code": "FORBIDDEN"})
    return {"expired": await svc.expire_due(s, UUID(a.tenant_id))}


@router.post("/work-permits/{permit_id}/activate")
async def activate_permit(permit_id: UUID, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    try:
        return {"id": str(permit_id), "status": await svc.activate_permit(s, UUID(a.tenant_id), UUID(a.user_id), permit_id)}
    except (WP.PermitError, NotFound) as e:
        raise _http(e) from e


@router.get("/activities/{activity_id}/coverage")
async def coverage(activity_id: UUID, asset_type: str, required_units: float | None = None,
                   a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    try:
        r = await svc.coverage(s, UUID(a.tenant_id), activity_id, asset_type, required_units)
    except NotFound as e:
        raise _http(e) from e
    return {"state": r.state.value, "required_units": r.required_units, "available_units": r.available_units, "gap": r.gap,
            "counted": list(r.counted), "excluded": [{"asset_id": i, "reason": why} for i, why in r.excluded]}


@router.post("/temporary-assignments", status_code=201)
async def propose_assignment(b: AssignmentIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    try:
        return {"id": str(await svc.propose_assignment(s, UUID(a.tenant_id), UUID(a.user_id), b.model_dump(mode="python"))),
                "status": "proposed"}
    except CV.CoverageError as e:
        raise _http(e) from e


@router.post("/temporary-assignments/{assignment_id}/verify")
async def verify_assignment(assignment_id: UUID, b: VerifyIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    try:
        return {"id": str(assignment_id), "status": await svc.verify_assignment(
            s, UUID(a.tenant_id), UUID(a.user_id), assignment_id, b.inspection_id, b.physical_check_ok)}
    except (CV.CoverageError, NotFound) as e:
        raise _http(e) from e


@router.get("/audit/verify")
async def audit_verify(a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    v = await svc.verify_audit_chain(s, UUID(a.tenant_id))
    return {"valid": v.valid, "checked": v.checked, "first_bad_seq": v.first_bad_seq, "reason": v.reason}


# ---- Webhook Meta: firma HMAC sobre el cuerpo crudo + idempotencia. Entregado/leído NUNCA aprueba. ----
@router.get("/webhooks/meta")
async def meta_verify(request: Request):
    q = request.query_params
    try:
        return Response(NT.verify_subscription(q.get("hub.mode"), q.get("hub.verify_token"), q.get("hub.challenge"),
                                               os.environ.get("WHATSAPP_VERIFY_TOKEN")), media_type="text/plain")
    except NT.WebhookError as e:
        raise HTTPException(403, {"code": "WEBHOOK_VERIFY_FAILED"}) from e


@router.post("/webhooks/meta", status_code=200)
async def meta_webhook(request: Request):
    raw = await request.body()
    try:
        NT.verify_meta_signature(raw, request.headers.get("x-hub-signature-256"), os.environ.get("WHATSAPP_APP_SECRET"))
    except NT.WebhookError as e:
        raise HTTPException(401, {"code": str(e)}) from e
    import json
    from datetime import timezone
    processed = 0
    for ev in NT.extract_status_events(json.loads(raw)):
        if not (ev.tenant_id and ev.attempt_id and ev.status in ("sent", "delivered", "read", "failed")):
            continue
        async with get_session_factory()() as s, s.begin():
            await s.execute(text("SELECT set_config('app.current_tenant_id', :t, true)"), {"t": ev.tenant_id})
            fresh = await s.execute(text("INSERT INTO sst_webhook_events(tenant_id,event_id) VALUES (:t,:e) ON CONFLICT DO NOTHING RETURNING 1"),
                                    {"t": ev.tenant_id, "e": ev.event_id})
            if fresh.first() is None or NT.is_replay(ev, set(), datetime.now(timezone.utc)):
                continue
            await s.execute(text("UPDATE sst_notification_attempts SET status=:st,response=CAST(:r AS jsonb) "
                                 "WHERE tenant_id=:t AND id=:a"), {"st": ev.status, "t": ev.tenant_id, "a": ev.attempt_id,
                                                                   "r": json.dumps({"event_id": ev.event_id})})
            processed += 1
    return {"processed": processed}
