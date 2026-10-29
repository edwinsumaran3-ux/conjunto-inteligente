"""Finance API: payments and deterministic settlement."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session
from backend.app.modules.finance.application.payment_service import PaymentService
from backend.app.modules.finance.application.payment_posting_service import PaymentPostingService
from backend.app.modules.finance.schemas import AllocationIn, CreatePaymentIn

router=APIRouter(prefix='/finance',tags=['finance'])
service=PaymentService()
posting=PaymentPostingService()

@router.post('/payments',status_code=201)
async def create_payment(cmd:CreatePaymentIn,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    try:
        pid=await posting.create_and_post(session,UUID(auth.tenant_id),UUID(auth.user_id),company_id=cmd.company_id,partner_id=cmd.partner_id,treasury_account_id=cmd.treasury_account_id,direction=cmd.direction,payment_date=cmd.payment_date,amount=cmd.amount,currency=cmd.currency,idempotency_key=cmd.idempotency_key,external_reference=cmd.external_reference)
        return {'id':str(pid),'status':'POSTED'}
    except (ValueError,RuntimeError) as exc:
        raise HTTPException(status_code=409 if 'idempotency' in str(exc).lower() else 422,detail={'code':'PAYMENT_REJECTED','message':str(exc)}) from exc

@router.post('/payment-allocations',status_code=204)
async def allocate_payment(cmd:AllocationIn,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    try: await service.allocate(session,UUID(auth.tenant_id),cmd.payment_id,cmd.receivable_payable_id,cmd.amount)
    except ValueError as exc: raise HTTPException(status_code=422,detail={'code':'ALLOCATION_REJECTED','message':str(exc)}) from exc

from backend.app.modules.finance.application.payment_reversal_service import PaymentReversalService
from pydantic import BaseModel, Field

reversal_service=PaymentReversalService()

class PaymentReversalIn(BaseModel):
    reason: str = Field(min_length=1,max_length=1000)

@router.post('/payments/{payment_id}/reverse', status_code=201)
async def reverse_payment(payment_id:UUID,cmd:PaymentReversalIn,auth:AuthContext=Depends(get_auth_context),session=Depends(get_tenant_session)):
    try:
        rid=await reversal_service.reverse(session,UUID(auth.tenant_id),payment_id,UUID(auth.user_id),cmd.reason)
        return {'reversal_payment_id':str(rid),'status':'REVERSED'}
    except ValueError as exc:
        raise HTTPException(status_code=422,detail={'code':'PAYMENT_REVERSAL_REJECTED','message':str(exc)}) from exc
