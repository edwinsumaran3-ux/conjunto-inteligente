"""Fail-closed JWT authentication and tenant-scoped database dependencies."""
from dataclasses import dataclass
from typing import Any
from uuid import UUID
from fastapi import HTTPException, Request, Depends
from sqlalchemy import text
from backend.app.core.security import decode_access_token

@dataclass(frozen=True)
class AuthContext:
    tenant_id: str
    subject_id: str
    permissions: frozenset[str] = frozenset()
    roles: frozenset[str] = frozenset()
    @property
    def user_id(self) -> str:
        return self.subject_id

async def get_auth_context(request: Request) -> AuthContext:
    ctx = getattr(request.state, "auth_context", None)
    if isinstance(ctx, AuthContext): return ctx
    authorization=request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate":"Bearer"})
    token=authorization[7:].strip()
    try:
        claims=decode_access_token(token)
        tenant_id=str(UUID(str(claims["tenant_id"])))
        subject_id=str(UUID(str(claims["sub"])))
        roles=frozenset(str(x) for x in claims.get("roles", []) if isinstance(x,str))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid access token", headers={"WWW-Authenticate":"Bearer"}) from exc
    ctx=AuthContext(tenant_id,subject_id,roles=roles)
    request.state.auth_context=ctx
    return ctx

async def get_tenant_session(request: Request, auth: AuthContext = Depends(get_auth_context)):
    factory=getattr(request.app.state,"tenant_session_factory",None)
    if factory is None:
        raise HTTPException(status_code=503,detail="Tenant database is not configured")
    async with factory() as session:
        try:
            await session.execute(text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                                  {"tenant_id":str(UUID(auth.tenant_id))})
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise
