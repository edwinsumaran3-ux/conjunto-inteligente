from uuid import UUID
from fastapi import APIRouter,Depends,status
from backend.app.api.deps import AuthContext,get_auth_context,get_tenant_session
from ..application.service import AccountingService
from ..application.catalog_service import CatalogService
from ..schemas.journal import JournalIn
from ..schemas.catalog import PeriodIn,AccountIn
router=APIRouter(prefix='/accounting',tags=['accounting']); accounting=AccountingService(); catalog=CatalogService()
@router.post('/periods',status_code=201)
async def create_period(cmd:PeriodIn,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    return {'id':str(await catalog.create_period(session,UUID(auth.tenant_id),cmd))}
@router.post('/accounts',status_code=201)
async def create_account(cmd:AccountIn,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    return {'id':str(await catalog.create_account(session,UUID(auth.tenant_id),cmd))}
@router.post('/periods/{period_id}/close',status_code=status.HTTP_204_NO_CONTENT)
async def close_period(period_id:UUID,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    await catalog.close_period(session,UUID(auth.tenant_id),period_id,UUID(auth.user_id))
@router.post('/journals',status_code=201)
async def post_journal(cmd:JournalIn,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    eid=await accounting.post_journal(session,UUID(auth.tenant_id),UUID(auth.user_id),cmd)
    from backend.app.platform.realtime.service import publish
    await publish(session,tenant_id=UUID(auth.tenant_id),topic='accounting.journal.posted',payload={'entry_id':str(eid),'source_type':getattr(cmd,'source_type',None)},correlation_id=str(eid))
    return {'id':str(eid),'status':'POSTED'}
