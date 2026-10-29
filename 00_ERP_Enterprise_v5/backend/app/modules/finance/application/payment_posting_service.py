"""Payment creation, posting and ledger settlement with idempotent semantics."""
from __future__ import annotations
import json
from datetime import date
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.idempotency import fingerprint, reserve, complete
from backend.app.modules.accounting.application.posting_service import AccountingPostingService


class PaymentPostingService:
    async def create_and_post(self, session: AsyncSession, tenant_id: UUID, actor_id: UUID, *,
                              company_id: UUID | None, partner_id: UUID | None, treasury_account_id: UUID,
                              direction: str, payment_date: date, amount: Decimal, currency: str,
                              idempotency_key: str, external_reference: str | None = None) -> UUID:
        if amount <= 0: raise ValueError("payment amount must be positive")
        direction = direction.upper()
        if direction not in {"RECEIPT", "DISBURSEMENT"}: raise ValueError("invalid payment direction")
        currency = currency.upper()
        payload = {"company_id": str(company_id) if company_id else None, "partner_id": str(partner_id) if partner_id else None,
                   "treasury_account_id": str(treasury_account_id), "direction": direction, "payment_date": str(payment_date),
                   "amount": str(amount), "currency": currency, "external_reference": external_reference}
        route = "POST:/finance/payments"
        result = await reserve(session, tenant_id, idempotency_key, route, fingerprint(payload))
        if result.status == "completed": return UUID(str(result.response_body["id"]))
        if result.status == "in_progress": raise RuntimeError("payment idempotency key is already in progress")
        treasury = (await session.execute(text("""
            SELECT id,ledger_account_id,currency,active FROM treasury_accounts
            WHERE tenant_id=:t AND id=:a FOR UPDATE
        """), {"t": tenant_id, "a": treasury_account_id})).mappings().one_or_none()
        if not treasury or not treasury["active"]: raise ValueError("treasury account not found or inactive")
        if treasury["currency"] != currency: raise ValueError("treasury account currency mismatch")
        if not treasury["ledger_account_id"]: raise ValueError("treasury ledger account is not configured")
        operation = direction
        profile = (await session.execute(text("""
            SELECT debit_account_id,credit_account_id FROM accounting_posting_profiles
            WHERE tenant_id=:t AND company_id IS NOT DISTINCT FROM :c AND operation=:o AND currency=:cur AND active
              AND effective_from<=:d AND (effective_to IS NULL OR effective_to>=:d)
            ORDER BY effective_from DESC LIMIT 1
        """), {"t": tenant_id, "c": company_id, "o": operation, "cur": currency, "d": payment_date})).mappings().one_or_none()
        if not profile: raise ValueError(f"payment posting profile not configured: {operation}/{currency}")
        period = (await session.execute(text("""
            SELECT id FROM accounting_periods WHERE tenant_id=:t AND starts_on<=:d AND ends_on>=:d AND status='OPEN'
            ORDER BY starts_on DESC LIMIT 1 FOR UPDATE
        """), {"t": tenant_id, "d": payment_date})).scalar_one_or_none()
        if not period: raise ValueError("no open accounting period for payment date")
        if direction == "RECEIPT":
            debit, credit = treasury["ledger_account_id"], profile["credit_account_id"]
        else:
            debit, credit = profile["debit_account_id"], treasury["ledger_account_id"]
        if not debit or not credit: raise ValueError("payment posting accounts are incomplete")
        payment_id = await session.scalar(text("""
            INSERT INTO payments(tenant_id,company_id,partner_id,direction,payment_date,amount,currency,treasury_account_id,external_reference,status,idempotency_key,created_by)
            VALUES(:t,:c,:p,:dir,:d,:a,:cur,:ta,:ext,'DRAFT',:key,:u) RETURNING id
        """), {"t":tenant_id,"c":company_id,"p":partner_id,"dir":direction,"d":payment_date,"a":amount,"cur":currency,"ta":treasury_account_id,"ext":external_reference,"key":idempotency_key,"u":actor_id})
        lines=[{"account_id":str(debit),"debit":str(amount),"credit":"0","currency":currency,"description":f"{direction} treasury"},
               {"account_id":str(credit),"debit":"0","credit":str(amount),"currency":currency,"description":f"{direction} settlement"}]
        entry=await session.scalar(text("SELECT post_journal(:t,:p,:d,:desc,'PAYMENT',:src,:u,CAST(:lines AS jsonb))"),
            {"t":tenant_id,"p":period,"d":payment_date,"desc":f"Payment {payment_id}","src":payment_id,"u":actor_id,"lines":json.dumps(lines)})
        await session.execute(text("UPDATE payments SET status='POSTED',journal_entry_id=:j,posted_at=now() WHERE tenant_id=:t AND id=:p"),{"j":entry,"t":tenant_id,"p":payment_id})
        await session.execute(text("""
            INSERT INTO treasury_movements(tenant_id,treasury_account_id,movement_date,direction,amount,currency,reference,payment_id,journal_entry_id,status)
            VALUES(:t,:a,:d,:md,:amt,:cur,:ref,:p,:j,'POSTED')
        """), {"t":tenant_id,"a":treasury_account_id,"d":payment_date,"md":"IN" if direction=="RECEIPT" else "OUT","amt":amount,"cur":currency,"ref":external_reference,"p":payment_id,"j":entry})
        await complete(session, tenant_id, idempotency_key, route, 201, {"id":str(payment_id)})
        return UUID(str(payment_id))
