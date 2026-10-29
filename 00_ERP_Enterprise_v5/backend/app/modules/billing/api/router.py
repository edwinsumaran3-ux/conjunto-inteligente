from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session
from backend.app.modules.billing.application.invoice_service import BillingService
from backend.app.modules.billing.application.issue_service import InvoiceIssueService
from backend.app.modules.billing.schemas.invoice import CreateInvoiceInput, TransitionInput

router = APIRouter(prefix='/billing', tags=['billing'])
service = BillingService()
issuer = InvoiceIssueService()

@router.post('/invoices', status_code=201)
async def create_invoice(cmd: CreateInvoiceInput, auth: AuthContext = Depends(get_auth_context), session=Depends(get_tenant_session)):
    invoice_id = await service.create_draft(session, UUID(auth.tenant_id), UUID(auth.user_id), cmd)
    return {'id': str(invoice_id), 'status': 'DRAFT'}

@router.post('/invoices/{document_id}/calculated', status_code=204)
async def calculate_invoice(document_id: UUID, cmd: TransitionInput = TransitionInput(), auth: AuthContext = Depends(get_auth_context), session=Depends(get_tenant_session)):
    await service.transition(session, UUID(auth.tenant_id), UUID(auth.user_id), document_id, 'CALCULATED', cmd.reason)

@router.post('/invoices/{document_id}/ready', status_code=204)
async def ready_invoice(document_id: UUID, cmd: TransitionInput = TransitionInput(), auth: AuthContext = Depends(get_auth_context), session=Depends(get_tenant_session)):
    await service.transition(session, UUID(auth.tenant_id), UUID(auth.user_id), document_id, 'READY', cmd.reason)

@router.post('/invoices/{document_id}/submitting', status_code=204)
async def mark_submitting(document_id: UUID, cmd: TransitionInput = TransitionInput(), auth: AuthContext = Depends(get_auth_context), session=Depends(get_tenant_session)):
    await service.transition(session, UUID(auth.tenant_id), UUID(auth.user_id), document_id, 'SUBMITTING', cmd.reason)


@router.post('/invoices/{document_id}/post', status_code=201)
async def post_invoice(document_id: UUID, auth: AuthContext = Depends(get_auth_context), session=Depends(get_tenant_session)):
    try:
        entry = await issuer.issue(session, UUID(auth.tenant_id), document_id, UUID(auth.user_id))
        from backend.app.platform.realtime.service import publish   # misma transacción: si la factura no se confirma, el evento tampoco
        await publish(session, tenant_id=UUID(auth.tenant_id), topic='billing.invoice.posted', payload={'document_id': str(document_id), 'journal_entry_id': str(entry)}, correlation_id=str(document_id))
        return {'journal_entry_id': str(entry), 'status': 'POSTED'}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={'code':'INVOICE_POST_REJECTED','message':str(exc)}) from exc


@router.post('/invoices/{document_id}/submit')
async def submit_to_dian(document_id: UUID, auth: AuthContext = Depends(get_auth_context), session=Depends(get_tenant_session)):
    """SUBMITTING -> (transporte DIAN) -> VALIDATED | REJECTED. Sin transporte configurado: 503 y el documento NO cambia."""
    import asyncio, os
    from sqlalchemy import text
    from backend.app.modules.billing.application.dian_transport import get_transport, validate_response
    t, u = UUID(auth.tenant_id), UUID(auth.user_id)
    if not ({'admin', 'administrator', 'accountant', 'finance_admin', 'billing_operator'} & set(auth.roles)): raise HTTPException(403, {'code': 'BILLING_ROLE_REQUIRED'})
    transport = get_transport()                       # falla cerrado ANTES de tocar nada
    doc = (await session.execute(text("SELECT id,lifecycle_status,document_type,series,number,total_amount,currency FROM financial_documents WHERE tenant_id=:t AND id=:d FOR UPDATE"), {'t': t, 'd': document_id})).mappings().first()
    if not doc: raise HTTPException(404, 'document not found')
    if doc['lifecycle_status'] != 'SUBMITTING': raise HTTPException(409, {'code': 'DOCUMENT_NOT_SUBMITTING', 'status': doc['lifecycle_status']})
    try: resp = validate_response(await asyncio.wait_for(transport.submit(dict(doc)), timeout=float(os.getenv('DIAN_TIMEOUT_SECONDS', '20'))))
    except HTTPException: raise
    except asyncio.TimeoutError: raise HTTPException(504, {'code': 'DIAN_TIMEOUT'})
    except Exception as e: raise HTTPException(502, {'code': 'DIAN_TRANSPORT_ERROR', 'detail': type(e).__name__}) from e
    attempt = (await session.execute(text("SELECT COALESCE(max(attempt),0)+1 FROM dian_submissions WHERE tenant_id=:t AND document_id=:d"), {'t': t, 'd': document_id})).scalar_one()
    await session.execute(text("""INSERT INTO dian_submissions(tenant_id,document_id,attempt,outcome,response_code,response_description,response_hash,external_id,submitted_by)
        VALUES(:t,:d,:a,:o,:c,:ds,:h,:x,:u)"""), {'t': t, 'd': document_id, 'a': attempt, 'o': resp.outcome, 'c': resp.response_code, 'ds': resp.response_description, 'h': resp.response_hash, 'x': resp.external_id, 'u': u})
    target = 'VALIDATED' if resp.outcome == 'ACCEPTED' else 'REJECTED'
    await session.execute(text("SELECT transition_financial_document(:t,:d,:tg,:u,:r)"), {'t': t, 'd': document_id, 'tg': target, 'u': u, 'r': f'DIAN {resp.response_code}'})
    await session.execute(text("UPDATE financial_documents SET dian_status=:s WHERE tenant_id=:t AND id=:d"), {'s': target, 't': t, 'd': document_id})
    return {'status': target, 'attempt': attempt, 'external_id': resp.external_id}
