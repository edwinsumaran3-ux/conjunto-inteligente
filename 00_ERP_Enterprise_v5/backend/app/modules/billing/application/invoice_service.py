from __future__ import annotations
import hashlib, json
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.idempotency import reserve, complete, fingerprint
from backend.app.modules.billing.schemas.invoice import CreateInvoiceInput

CENT = Decimal('0.01')

class BillingService:
    async def create_draft(self, session: AsyncSession, tenant_id: UUID, user_id: UUID, cmd: CreateInvoiceInput) -> UUID:
        if cmd.due_date < cmd.issue_date:
            raise ValueError('due_date must be on or after issue_date')
        payload = cmd.model_dump(mode='json')
        request_hash = fingerprint(payload)
        route = 'POST:/billing/invoices'
        idem = await reserve(session, tenant_id, cmd.idempotency_key, route, request_hash)
        if idem.status == 'completed':
            return UUID(str(idem.response_body['id']))
        if idem.status == 'in_progress':
            raise RuntimeError('request with this idempotency key is already in progress')

        number = await session.scalar(text('SELECT allocate_document_number(:t,NULL,\'INVOICE\',:s)'), {'t': tenant_id, 's': cmd.series})
        if number is None:
            raise RuntimeError('document numbering sequence is not configured')
        subtotal = Decimal('0')
        tax_total = Decimal('0')
        line_values: list[tuple] = []
        tax_values: list[tuple] = []
        for idx, line in enumerate(cmd.lines, 1):
            line_subtotal = (line.quantity * line.unit_price).quantize(CENT, ROUND_HALF_UP)
            subtotal += line_subtotal
            line_tax = Decimal('0')
            for tax in line.taxes:
                amount = (line_subtotal * tax.rate / Decimal('100')).quantize(CENT, ROUND_HALF_UP)
                line_tax += amount
                tax_values.append((idx, tax.code, tax.rate, line_subtotal, amount))
            tax_total += line_tax
            line_values.append((idx, line, line_subtotal, line_tax))
        total = subtotal + tax_total
        doc_id = UUID(str(await session.scalar(text("""
            INSERT INTO financial_documents
              (tenant_id,partner_id,direction,document_type,series,number,issue_date,due_date,currency,exchange_rate,subtotal,tax_amount,total_amount,balance_amount,lifecycle_status,created_by,source_type,source_id)
            VALUES (:t,:p,'AR','INVOICE',:s,:n,:d,:dd,:c,1,:sub,:tax,:total,:total,'DRAFT',:u,:st,:sid)
            RETURNING id
        """), {'t':tenant_id,'p':cmd.partner_id,'s':cmd.series,'n':str(number),'d':cmd.issue_date,'dd':cmd.due_date,'c':cmd.currency,'sub':subtotal,'tax':tax_total,'total':total,'u':user_id,'st':cmd.source_type,'sid':cmd.source_id})))
        for idx, line, line_subtotal, line_tax in line_values:
            line_id = await session.scalar(text("""
                INSERT INTO financial_document_lines(tenant_id,financial_document_id,line_no,description,quantity,unit_price,account_id,line_subtotal,tax_amount)
                VALUES(:t,:d,:n,:desc,:q,:p,:a,:sub,:tax) RETURNING id
            """), {'t':tenant_id,'d':doc_id,'n':idx,'desc':line.description,'q':line.quantity,'p':line.unit_price,'a':line.account_id,'sub':line_subtotal,'tax':line_tax})
            for tax_line in [x for x in tax_values if x[0] == idx]:
                _, code, rate, base, amount = tax_line
                await session.execute(text("""
                    INSERT INTO financial_document_taxes(tenant_id,financial_document_id,line_id,tax_code,rate,base_amount,tax_amount)
                    VALUES(:t,:d,:l,:code,:rate,:base,:amount)
                """), {'t':tenant_id,'d':doc_id,'l':line_id,'code':code,'rate':rate,'base':base,'amount':amount})
        # AR/AP is created only when the document is actually posted. A DRAFT is not
        # an accounting receivable/payable and must not affect financial balances.
        await complete(session, tenant_id, cmd.idempotency_key, route, 201, {'id': str(doc_id)})
        return doc_id

    async def transition(self, session: AsyncSession, tenant_id: UUID, user_id: UUID, document_id: UUID, target: str, reason: str | None) -> None:
        await session.execute(text('SELECT transition_financial_document(:t,:d,:s,:u,:r)'), {'t':tenant_id,'d':document_id,'s':target,'u':user_id,'r':reason})
