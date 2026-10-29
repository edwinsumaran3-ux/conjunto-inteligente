"""Alta/confirmación/baja de TOTP (paso adicional para aprobaciones SST). El secreto se cifra con Fernet (TOTP_ENCRYPTION_KEY) y se muestra UNA vez."""
from __future__ import annotations
import base64, hmac, os, secrets, time
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session
from backend.app.platform.security.strong_auth import _decrypt_secret, _totp

router = APIRouter(prefix="/mfa", tags=["mfa"])
class CodeIn(BaseModel):
    code: str = Field(pattern="^[0-9]{6}$")

def _fernet():
    key = os.getenv("TOTP_ENCRYPTION_KEY")
    if not key: raise HTTPException(503, {"code": "TOTP_ENCRYPTION_KEY_NOT_CONFIGURED"})
    from cryptography.fernet import Fernet
    return Fernet(key.encode())

def _valid(secret: bytes, code: str, digits=6, period=30) -> bool:
    now = int(time.time()); return any(hmac.compare_digest(_totp(secret, now + k * period, digits, period), code) for k in (-1, 0, 1))

@router.post("/enroll", status_code=201)
async def enroll(a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    f = _fernet(); t, u = UUID(a.tenant_id), UUID(a.user_id)
    cur = (await s.execute(text("SELECT is_enabled FROM user_totp_credentials WHERE tenant_id=:t AND user_id=:u FOR UPDATE"), {"t": t, "u": u})).scalar_one_or_none()
    if cur: raise HTTPException(409, {"code": "MFA_ALREADY_ENABLED"})
    raw = secrets.token_bytes(20)
    await s.execute(text("""INSERT INTO user_totp_credentials(tenant_id,user_id,encrypted_secret,is_enabled) VALUES(:t,:u,:s,false)
        ON CONFLICT(tenant_id,user_id) DO UPDATE SET encrypted_secret=EXCLUDED.encrypted_secret, is_enabled=false"""), {"t": t, "u": u, "s": f.encrypt(raw).decode()})
    b32 = base64.b32encode(raw).decode().rstrip("=")
    return {"secret_base32": b32, "otpauth_uri": f"otpauth://totp/ConjuntoInteligente:{a.user_id}?secret={b32}&issuer=ConjuntoInteligente&digits=6&period=30", "status": "pending_confirmation"}

@router.post("/confirm", status_code=204)
async def confirm(c: CodeIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    t, u = UUID(a.tenant_id), UUID(a.user_id)
    row = (await s.execute(text("SELECT encrypted_secret,is_enabled FROM user_totp_credentials WHERE tenant_id=:t AND user_id=:u FOR UPDATE"), {"t": t, "u": u})).mappings().first()
    if not row: raise HTTPException(404, {"code": "MFA_NOT_ENROLLED"})
    if row["is_enabled"]: raise HTTPException(409, {"code": "MFA_ALREADY_ENABLED"})
    if not _valid(_decrypt_secret(row["encrypted_secret"]), c.code): raise HTTPException(422, {"code": "MFA_CODE_INVALID"})
    await s.execute(text("UPDATE user_totp_credentials SET is_enabled=true WHERE tenant_id=:t AND user_id=:u"), {"t": t, "u": u})

@router.post("/disable", status_code=204)
async def disable(c: CodeIn, a: AuthContext = Depends(get_auth_context), s=Depends(get_tenant_session)):
    t, u = UUID(a.tenant_id), UUID(a.user_id)
    row = (await s.execute(text("SELECT encrypted_secret FROM user_totp_credentials WHERE tenant_id=:t AND user_id=:u AND is_enabled=true FOR UPDATE"), {"t": t, "u": u})).mappings().first()
    if not row: raise HTTPException(404, {"code": "MFA_NOT_ENABLED"})
    if not _valid(_decrypt_secret(row["encrypted_secret"]), c.code): raise HTTPException(422, {"code": "MFA_CODE_INVALID"})
    await s.execute(text("DELETE FROM user_totp_credentials WHERE tenant_id=:t AND user_id=:u"), {"t": t, "u": u})
