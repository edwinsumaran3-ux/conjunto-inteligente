"""Password hashing and short-lived JWT access tokens.

Set SECRET_KEY to a random secret of at least 32 bytes in production. Never use a
checked-in default. Password hashes use Argon2id via argon2-cffi.
"""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from typing import Iterable
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()

def _secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY")
    if not secret or len(secret.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET_KEY (or SECRET_KEY) must contain at least 32 bytes")
    return secret

def hash_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError("password must contain at least 12 characters")
    return _hasher.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    if not isinstance(password, str) or not isinstance(password_hash, str) or not password_hash:
        return False
    try:
        return bool(_hasher.verify(password_hash, password))
    except (VerifyMismatchError, VerificationError, InvalidHashError, ValueError, TypeError):
        return False

def create_access_token(subject: str, tenant_id: str, roles: Iterable[str] = ()) -> str:
    if not subject or not tenant_id:
        raise ValueError("subject and tenant_id are required")
    now = datetime.now(timezone.utc)
    try:
        ttl = int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "900"))
    except ValueError as exc:
        raise RuntimeError("ACCESS_TOKEN_TTL_SECONDS must be an integer") from exc
    if not 60 <= ttl <= 3600:
        raise RuntimeError("ACCESS_TOKEN_TTL_SECONDS must be between 60 and 3600")
    payload = {"sub": str(subject), "tenant_id": str(tenant_id), "roles": sorted(set(roles)),
               "iat": now, "nbf": now, "exp": now + timedelta(seconds=ttl), "iss": os.getenv("JWT_ISSUER", "conjunto-inteligente")}
    return jwt.encode(payload, _secret(), algorithm="HS256")

def decode_access_token(token: str) -> dict:
    if not isinstance(token, str) or not token or len(token) > 8192:
        raise jwt.InvalidTokenError("invalid token")
    return jwt.decode(token, _secret(), algorithms=["HS256"], issuer=os.getenv("JWT_ISSUER", "conjunto-inteligente"),
                      options={"require": ["sub", "tenant_id", "iat", "exp", "iss"]})
