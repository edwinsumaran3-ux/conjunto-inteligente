from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.app.core.idempotency import fingerprint
from backend.app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from backend.app.core.security_policies import SecurityPolicyViolation, validate_login_identifier
from backend.app.models import Base
from backend.app.models.tenant import Tenant
from backend.app.models.user import User


def test_password_hash_round_trip_and_rejects_wrong_password():
    encoded = hash_password("this-is-a-strong-test-password")
    assert encoded.startswith("$argon2id$")
    assert verify_password("this-is-a-strong-test-password", encoded)
    assert not verify_password("wrong-password", encoded)
    assert not verify_password("anything", "not-a-valid-hash")


def test_password_hash_rejects_short_password():
    with pytest.raises(ValueError):
        hash_password("short")


def test_jwt_contains_subject_tenant_roles_and_expires(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "v11-test-secret-that-is-long-enough-for-hs256")
    tenant_id, user_id = str(uuid4()), str(uuid4())
    token = create_access_token(user_id, tenant_id, ["ADMIN"])
    claims = decode_access_token(token)
    assert claims["sub"] == user_id
    assert claims["tenant_id"] == tenant_id
    assert claims["roles"] == ["ADMIN"]
    assert "exp" in claims


def test_jwt_rejects_expired_access_token(monkeypatch):
    secret = "v11-test-secret-that-is-long-enough-for-hs256"
    monkeypatch.setenv("JWT_SECRET_KEY", secret)
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "tenant_id": str(uuid4()),
            "iat": now - timedelta(minutes=20),
            "nbf": now - timedelta(minutes=20),
            "exp": now - timedelta(minutes=5),
            "iss": "conjunto-inteligente",
        },
        secret,
        algorithm="HS256",
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_jwt_rejects_wrong_issuer_and_signature(monkeypatch):
    secret = "v11-test-secret-that-is-long-enough-for-hs256"
    monkeypatch.setenv("JWT_SECRET_KEY", secret)
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(uuid4()),
        "tenant_id": str(uuid4()),
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=15),
        "iss": "another-service",
    }
    token = jwt.encode(claims, secret, algorithm="HS256")
    with pytest.raises(jwt.InvalidIssuerError):
        decode_access_token(token)

    monkeypatch.setenv("JWT_SECRET_KEY", "a-different-secret-key-long-enough")
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(jwt.encode({**claims, "iss": "conjunto-inteligente"}, secret, algorithm="HS256"))


def test_jwt_fails_closed_without_secret(monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        create_access_token(str(uuid4()), str(uuid4()), [])


def test_login_identifier_normalizes_case_and_whitespace():
    assert validate_login_identifier("  USER@EXAMPLE.COM ") == "user@example.com"
    with pytest.raises(SecurityPolicyViolation):
        validate_login_identifier("not-an-email")


def test_idempotency_fingerprint_is_canonical():
    assert fingerprint({"b": 2, "a": 1}) == fingerprint({"a": 1, "b": 2})
    assert fingerprint({"a": 1}) != fingerprint({"a": 2})


def test_identity_models_have_expected_tables_and_tenant_scoped_user_key():
    assert Tenant.__tablename__ == "tenants"
    assert User.__tablename__ == "users"
    assert "uq_users_tenant_email" in {constraint.name for constraint in User.__table__.constraints}
    assert "users" in Base.metadata.tables


def test_application_entrypoint_imports_and_exposes_health_routes():
    from backend.app.main import app
    paths = set(app.openapi()["paths"])  # robust: newer FastAPI nests included routers in app.routes
    assert "/healthz" in paths
    assert "/readyz" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/realtime/events" in paths


def test_api_responses_are_not_cacheable_even_when_authentication_fails():
    from backend.app.main import app

    middleware = next(
        entry for entry in app.user_middleware
        if entry.cls is BaseHTTPMiddleware and "dispatch" in entry.kwargs
    )
    dispatch = middleware.kwargs["dispatch"]
    request = SimpleNamespace(url=SimpleNamespace(path="/api/v1/digital-twin/overview"))

    async def call_next(_request):
        return Response(status_code=401)

    response = asyncio.run(dispatch(request, call_next))

    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"


def test_identity_migration_defines_tenant_rls_and_audit_immutability():
    from pathlib import Path
    migration = Path(__file__).resolve().parents[2] / "migrations/sql/20261011_003_identity_and_platform.sql"
    sql = migration.resolve().read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "app.current_tenant_id" in sql
    assert "audit_log_no_mutation" in sql
    assert "UPDATE/DELETE is forbidden" in sql
