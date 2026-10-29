from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.exceptions import AuthenticationError
from backend.app.core.security import create_access_token, verify_password
from backend.app.core.security_policies import SecurityPolicyViolation, validate_login_identifier
from backend.app.models.tenant import Tenant
from backend.app.models.user import User


class LoginService:
    async def execute(self, session: AsyncSession, email: str, password: str, tenant_id: str) -> str:
        try:
            tid = UUID(tenant_id)
            normalized_email = validate_login_identifier(email)
        except (ValueError, TypeError, SecurityPolicyViolation):
            raise AuthenticationError("Invalid credentials")

        async with session.begin():
            await session.execute(text("SELECT set_config('app.current_tenant_id', :tenant_id, true), set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tid)})
            tenant = await session.scalar(select(Tenant).where(Tenant.id == tid, Tenant.is_active.is_(True)))
            user = await session.scalar(
                select(User).where(User.email == normalized_email, User.tenant_id == tid, User.is_active.is_(True))
            )
            if tenant is None or user is None or not verify_password(password, user.password_hash):
                raise AuthenticationError("Invalid credentials")
            roles = tuple(
                (
                    await session.execute(
                        text("""
                            SELECT r.name
                            FROM roles r
                            JOIN user_roles ur ON ur.role_id=r.id
                            WHERE ur.user_id=:uid AND r.tenant_id=:tid
                            ORDER BY r.name
                        """),
                        {"uid": user.id, "tid": tid},
                    )
                ).scalars().all()
            )
            return create_access_token(str(user.id), str(tid), list(roles))
