from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/current")
async def get_current_tenant(
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant = (
        await session.execute(
            text(
                """SELECT id,name,is_active,created_at
                   FROM tenants WHERE id=:tenant"""
            ),
            {"tenant": auth.tenant_id},
        )
    ).mappings().first()
    if tenant is None:
        raise HTTPException(404, detail={"code": "TENANT_NOT_FOUND"})
    return dict(tenant)
