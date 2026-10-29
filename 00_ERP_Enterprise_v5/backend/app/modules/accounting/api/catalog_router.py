from uuid import UUID
from fastapi import APIRouter,Depends,status
from backend.app.api.deps import AuthContext,get_auth_context,get_tenant_session
from ..application.catalog_service import CatalogService
from ..schemas.catalog import PeriodIn,AccountIn
router=APIRouter(prefix='/accounting',tags=['accounting'])
svc=CatalogService()
@router.post('/periods',status_code=status.HTTP_201_CREATED)
async def create_period(cmd:PeriodIn,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    return {'id':str(await svc.create_period(session,UUID(auth.tenant_id),cmd))}
@router.post('/accounts',status_code=status.HTTP_201_CREATED)
async def create_account(cmd:AccountIn,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    return {'id':str(await svc.create_account(session,UUID(auth.tenant_id),cmd))}
@router.post('/periods/{period_id}/close',status_code=status.HTTP_204_NO_CONTENT)
async def close_period(period_id:UUID,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    await svc.close_period(session,UUID(auth.tenant_id),period_id,UUID(auth.user_id))
