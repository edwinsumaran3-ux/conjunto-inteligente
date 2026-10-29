"""Canal de entrega del token de aprobación (el token en claro NUNCA se persiste ni se devuelve al solicitante).
Falla CERRADO: sin canal configurado la aprobación no se crea (si no, quedaría pendiente para siempre sin que el aprobador la reciba).
Configuración: SST_APPROVAL_WEBHOOK_URL + SST_APPROVAL_WEBHOOK_SECRET (HMAC-SHA256 en X-Signature) o set_notifier() desde un adaptador propio."""
from __future__ import annotations
import asyncio, hashlib, hmac, json, os, urllib.request
from typing import Protocol
from fastapi import HTTPException

class ApprovalNotifier(Protocol):
    async def deliver(self, *, tenant_id: str, approval_id: str, recipient_id: str, token: str, expires_at: str | None) -> None: ...

class WebhookNotifier:
    def __init__(self, url: str, secret: str, timeout: float = 5.0): self.url, self.secret, self.timeout = url, secret.encode(), timeout
    async def deliver(self, *, tenant_id, approval_id, recipient_id, token, expires_at):
        body = json.dumps({"event": "sst.approval.token_issued", "tenant_id": tenant_id, "approval_id": approval_id, "recipient_id": recipient_id, "token": token, "expires_at": expires_at}, separators=(",", ":")).encode()
        sig = hmac.new(self.secret, body, hashlib.sha256).hexdigest()
        req = urllib.request.Request(self.url, data=body, method="POST", headers={"Content-Type": "application/json", "X-Signature": sig})
        def _send():
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                if not 200 <= r.status < 300: raise RuntimeError(f"notifier status {r.status}")
        await asyncio.to_thread(_send)

_custom: ApprovalNotifier | None = None
def set_notifier(n: ApprovalNotifier | None) -> None:
    global _custom; _custom = n
def get_notifier() -> ApprovalNotifier:
    if _custom is not None: return _custom
    url, secret = os.getenv("SST_APPROVAL_WEBHOOK_URL"), os.getenv("SST_APPROVAL_WEBHOOK_SECRET", "")
    if url and len(secret) >= 24:
        if not url.startswith("https://") and os.getenv("APP_ENV", "dev") == "production": raise HTTPException(503, {"code": "APPROVAL_NOTIFIER_INSECURE_URL"})
        return WebhookNotifier(url, secret)
    raise HTTPException(503, {"code": "APPROVAL_NOTIFIER_NOT_CONFIGURED"})
