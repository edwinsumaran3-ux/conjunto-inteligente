"""Reintentos/escalamiento y webhook de Meta (spec §8). Entregado/leído NO es aprobado."""
from __future__ import annotations
import hashlib, hmac
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping

CHANNELS = ("portal", "whatsapp", "email", "sms", "voice")
BACKOFF_MINUTES = (5, 15, 60)
MAX_ATTEMPTS = 3


@dataclass(frozen=True, slots=True)
class RetryDecision:
    action: str  # retry | escalate_backup | give_up
    channel: str | None
    at: datetime | None
    regenerate_token: bool = False


def next_step(*, attempts: int, channel: str, last_attempt_at: datetime, now: datetime,
              has_backup: bool, approval_expired: bool, available: tuple[str, ...] = CHANNELS) -> RetryDecision:
    if approval_expired:
        return RetryDecision("give_up", None, None)  # queda 'expirada sin decisión'; el bloqueo se mantiene
    if attempts >= MAX_ATTEMPTS:
        return RetryDecision("escalate_backup" if has_backup else "give_up", None, None)
    due = last_attempt_at + timedelta(minutes=BACKOFF_MINUTES[min(attempts, len(BACKOFF_MINUTES)) - 1 if attempts else 0])
    if now < due:
        return RetryDecision("retry", channel, due)
    pool = [c for c in available if c in CHANNELS]
    nxt = channel
    if attempts >= 2 and pool:  # tras fallos repetidos se cambia de canal
        i = pool.index(channel) if channel in pool else -1
        nxt = pool[(i + 1) % len(pool)]
    return RetryDecision("retry", nxt, now, regenerate_token=True)  # el token anterior no se reutiliza


class WebhookError(PermissionError):
    pass


def verify_meta_signature(raw_body: bytes, header: str | None, app_secret: str | None) -> None:
    if not app_secret:
        raise WebhookError("WEBHOOK_SECRET_MISSING")  # sin secreto configurado: rechazo
    if not header or not header.startswith("sha256="):
        raise WebhookError("WEBHOOK_SIGNATURE_MISSING")
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, header[len("sha256="):]):
        raise WebhookError("WEBHOOK_SIGNATURE_INVALID")


def verify_subscription(mode: str | None, token: str | None, challenge: str | None, expected_token: str | None) -> str:
    if not expected_token or mode != "subscribe" or not token or not hmac.compare_digest(token, expected_token):
        raise WebhookError("WEBHOOK_VERIFY_FAILED")
    return challenge or ""


@dataclass(frozen=True, slots=True)
class StatusEvent:
    event_id: str
    provider_message_id: str
    status: str  # sent | delivered | read | failed
    occurred_at: datetime
    tenant_id: str | None = None   # viene de biz_opaque_callback_data (payload firmado)
    attempt_id: str | None = None


def extract_status_events(payload: Mapping[str, Any]) -> list[StatusEvent]:
    from datetime import timezone
    out: list[StatusEvent] = []
    for entry in payload.get("entry", []) or []:
        for ch in entry.get("changes", []) or []:
            for st in (ch.get("value", {}) or {}).get("statuses", []) or []:
                mid, s, ts = st.get("id"), st.get("status"), st.get("timestamp")
                if not (mid and s and ts):
                    continue
                tenant = attempt = None
                cb = st.get("biz_opaque_callback_data")
                if isinstance(cb, str) and cb.count(":") == 1:
                    tenant, attempt = cb.split(":")
                out.append(StatusEvent(f"{mid}:{s}:{ts}", str(mid), str(s),
                                       datetime.fromtimestamp(int(ts), tz=timezone.utc), tenant, attempt))
    return out


def is_replay(ev: StatusEvent, seen_ids: set[str], now: datetime, max_age: timedelta = timedelta(hours=24)) -> bool:
    return ev.event_id in seen_ids or (now - ev.occurred_at) > max_age
