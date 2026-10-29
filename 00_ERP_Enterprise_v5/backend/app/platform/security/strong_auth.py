"""Fail-closed TOTP verification for step-up approvals.

Secrets are encrypted at rest with Fernet. Configure TOTP_ENCRYPTION_KEY with a
Fernet key and provision `user_totp_credentials` through a controlled enrollment flow.
This module deliberately does not auto-enroll users or accept missing credentials.
"""
from __future__ import annotations
import base64, hashlib, hmac, os, struct, time
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

def _decrypt_secret(value: str) -> bytes:
    key=os.getenv("TOTP_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("TOTP_ENCRYPTION_KEY is required for strong authentication")
    try:
        from cryptography.fernet import Fernet
        raw=Fernet(key.encode()).decrypt(value.encode())
    except Exception as exc:
        raise RuntimeError("unable to decrypt TOTP secret; verify TOTP_ENCRYPTION_KEY") from exc
    return raw

def _totp(secret: bytes, at: int, digits: int=6, period: int=30) -> str:
    counter=at//period
    digest=hmac.new(secret, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset=digest[-1]&0x0f
    number=(struct.unpack(">I", digest[offset:offset+4])[0]&0x7fffffff)%(10**digits)
    return str(number).zfill(digits)

async def verify_totp_credential(session: AsyncSession, *, tenant_id: UUID, actor_id: UUID, code: str) -> bool:
    if not isinstance(code, str) or not code.isdigit() or len(code) not in (6,8):
        return False
    row=(await session.execute(text("""SELECT encrypted_secret, digits, period_seconds FROM user_totp_credentials
       WHERE tenant_id=:tenant AND user_id=:actor AND is_enabled=true"""),
       {"tenant":tenant_id,"actor":actor_id})).mappings().one_or_none()
    if row is None: return False
    secret=_decrypt_secret(str(row["encrypted_secret"]))
    digits=int(row["digits"]); period=int(row["period_seconds"])
    if digits != len(code) or not 15 <= period <= 120: return False
    now=int(time.time())
    # Small clock skew window; constant-time compare.
    return any(hmac.compare_digest(_totp(secret, now + shift*period, digits, period), code) for shift in (-1,0,1))
