from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from backend.app.api.deps import AuthContext, get_auth_context

def _request_with_state(state):
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": "GET", "scheme": "http", "path": "/", "raw_path": b"/",
             "query_string": b"", "headers": [], "client": ("test", 1),
             "server": ("test", 80), "state": state}
    return Request(scope)

@pytest.mark.asyncio
async def test_auth_context_fails_closed_without_middleware_identity():
    request = _request_with_state({})
    with pytest.raises(HTTPException) as exc:
        await get_auth_context(request)
    assert exc.value.status_code == 401

@pytest.mark.asyncio
async def test_auth_context_accepts_trusted_typed_identity():
    tenant = str(uuid4())
    request = _request_with_state({"auth_context": AuthContext(tenant, "user-1", frozenset({"twin:read"}))})
    ctx = await get_auth_context(request)
    assert ctx.tenant_id == tenant
    assert ctx.subject_id == "user-1"
    assert "twin:read" in ctx.permissions

@pytest.mark.asyncio
async def test_auth_context_rejects_invalid_tenant():
    request = _request_with_state({"auth_context": SimpleNamespace(tenant_id="not-a-uuid", subject_id="user")})
    with pytest.raises(HTTPException) as exc:
        await get_auth_context(request)
    assert exc.value.status_code == 401
