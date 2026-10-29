"""Aprobaciones y tokens de un solo uso (spec §8). El silencio NUNCA es aprobación."""
from __future__ import annotations
import hashlib, hmac, secrets
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum


class ApprovalError(PermissionError):
    def __init__(self, code: str, msg: str = ""):
        super().__init__(f"{code}: {msg}" if msg else code)
        self.code = code


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"


TERMINAL = frozenset({ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.CHANGES_REQUESTED,
                      ApprovalStatus.EXPIRED, ApprovalStatus.INVALIDATED})


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class Approval:
    id: str
    activity_id: str | None
    action: str
    requester_id: str
    primary_id: str
    backup_id: str | None
    requires_mfa: bool
    expires_at: datetime
    version: int = 1
    status: ApprovalStatus = ApprovalStatus.PENDING

    @property
    def approvers(self) -> frozenset[str]:
        return frozenset(x for x in (self.primary_id, self.backup_id) if x)

    @property
    def grants_authorization(self) -> bool:
        return self.status is ApprovalStatus.APPROVED


@dataclass(frozen=True, slots=True)
class TokenRecord:
    token_hash: str
    approval_id: str
    recipient_id: str
    action: str
    version: int
    expires_at: datetime
    used_at: datetime | None = None
    revoked: bool = False


def issue_token(approval: Approval, recipient_id: str, now: datetime, ttl_minutes: int = 15) -> tuple[str, TokenRecord]:
    """Devuelve (token_en_claro, registro). Solo el hash se persiste."""
    if not 1 <= ttl_minutes <= 60:
        raise ApprovalError("TOKEN_TTL", "TTL fuera de rango seguro (1..60 min)")
    if recipient_id not in approval.approvers:
        raise ApprovalError("RECIPIENT_NOT_APPROVER")
    if approval.status is not ApprovalStatus.PENDING:
        raise ApprovalError("APPROVAL_NOT_PENDING")
    raw = secrets.token_urlsafe(48)
    exp = min(now + timedelta(minutes=ttl_minutes), approval.expires_at)
    return raw, TokenRecord(hash_token(raw), approval.id, recipient_id, approval.action, approval.version, exp)


def validate_token(rec: TokenRecord | None, raw: str, *, approval: Approval, action: str, actor_id: str,
                   now: datetime, mfa_verified: bool) -> None:
    """Lanza ApprovalError ante cualquier anomalía. El consumo atómico lo hace la capa de persistencia."""
    if rec is None or not hmac.compare_digest(rec.token_hash, hash_token(raw)):
        raise ApprovalError("TOKEN_INVALID")
    if rec.revoked:
        raise ApprovalError("TOKEN_REVOKED")
    if rec.used_at is not None:
        raise ApprovalError("TOKEN_REPLAY")
    if rec.expires_at <= now:
        raise ApprovalError("TOKEN_EXPIRED")
    if rec.action != action:
        raise ApprovalError("TOKEN_ACTION_MISMATCH")
    if rec.approval_id != approval.id:
        raise ApprovalError("TOKEN_APPROVAL_MISMATCH")
    if rec.recipient_id != actor_id:
        raise ApprovalError("TOKEN_RECIPIENT_MISMATCH", "quien consume no es el destinatario")
    if rec.version != approval.version:
        raise ApprovalError("TOKEN_STALE_VERSION", "el alcance cambió; se requiere nueva solicitud")
    if approval.status is not ApprovalStatus.PENDING:
        raise ApprovalError("APPROVAL_NOT_PENDING")
    if approval.requires_mfa and not mfa_verified:
        raise ApprovalError("MFA_REQUIRED")


def decide(approval: Approval, *, actor_id: str, decision: str, justification: str | None, now: datetime,
           mfa_verified: bool) -> Approval:
    if approval.status is not ApprovalStatus.PENDING:
        raise ApprovalError("APPROVAL_NOT_PENDING")
    if approval.expires_at <= now:
        raise ApprovalError("APPROVAL_EXPIRED")
    if actor_id == approval.requester_id:
        raise ApprovalError("SELF_APPROVAL")
    if actor_id not in approval.approvers:
        raise ApprovalError("NOT_AUTHORIZED_APPROVER")
    if approval.requires_mfa and not mfa_verified:
        raise ApprovalError("MFA_REQUIRED")
    target = {"approve": ApprovalStatus.APPROVED, "reject": ApprovalStatus.REJECTED,
              "request_changes": ApprovalStatus.CHANGES_REQUESTED}.get(decision)
    if target is None:
        raise ApprovalError("DECISION_UNKNOWN")
    if target is not ApprovalStatus.APPROVED and not (justification or "").strip():
        raise ApprovalError("JUSTIFICATION_REQUIRED")
    return replace(approval, status=target)


def expire_if_due(approval: Approval, now: datetime) -> Approval:
    """Vencimiento sin decisión => EXPIRED (bloquea). Nunca APPROVED."""
    if approval.status is ApprovalStatus.PENDING and approval.expires_at <= now:
        return replace(approval, status=ApprovalStatus.EXPIRED)
    return approval


def invalidate_on_scope_change(approval: Approval, *, changed: set[str]) -> Approval:
    material = {"scope", "date", "zone", "risk", "documents", "contractor"}
    if approval.status in (ApprovalStatus.PENDING, ApprovalStatus.APPROVED) and changed & material:
        return replace(approval, status=ApprovalStatus.INVALIDATED, version=approval.version + 1)
    return approval
