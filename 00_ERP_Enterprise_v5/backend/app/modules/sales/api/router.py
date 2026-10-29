from uuid import UUID
from fastapi import APIRouter, Depends
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session
from backend.app.modules.sales.application.order_service import SalesOrderService
from backend.app.modules.sales.schemas.order import CreateSalesOrderInput
router=APIRouter(prefix='/sales',tags=['sales']); service=SalesOrderService()
@router.post('/orders',status_code=201)
async def create_order(cmd:CreateSalesOrderInput,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    oid=await service.create_draft(session,UUID(auth.tenant_id),UUID(auth.user_id),cmd); return {'id':str(oid),'status':'DRAFT'}
@router.post('/orders/{order_id}/confirm',status_code=204)
async def confirm_order(order_id:UUID,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)): await service.confirm(session,UUID(auth.tenant_id),order_id)
@router.post('/orders/{order_id}/fulfill',status_code=200)
async def fulfill_order(order_id:UUID,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    doc=await service.fulfill(session,UUID(auth.tenant_id),UUID(auth.user_id),order_id)
    from backend.app.platform.realtime.service import publish
    await publish(session,tenant_id=UUID(auth.tenant_id),topic='sales.order.fulfilled',payload={'order_id':str(order_id),'billing_document_id':str(doc)},correlation_id=str(order_id))
    return {'order_id':str(order_id),'status':'FULFILLED','billing_document_id':str(doc),'billing_status':'DRAFT'}
@router.post('/orders/{order_id}/cancel',status_code=204)
async def cancel_order(order_id:UUID,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)): await service.cancel(session,UUID(auth.tenant_id),order_id)
