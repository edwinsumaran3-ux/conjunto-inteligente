"""Controlled payment reversal with explicit linkage to the compensating payment."""
from __future__ import annotations
import json
from datetime import date
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class PaymentReversalService:
    async def reverse(self, session: AsyncSession, tenant_id: UUID, payment_id: UUID,
                      actor_id: UUID, reason: str) -> UUID:
        reason=reason.strip()
        if not reason or len(reason)>1000: raise ValueError("reversal reason is required")
        payment=(await session.execute(text("""
          SELECT * FROM payments WHERE tenant_id=:t AND id=:p FOR UPDATE
        """),{"t":tenant_id,"p":payment_id})).mappings().one_or_none()
        if not payment: raise ValueError("payment not found")
        if payment["status"] != "POSTED": raise ValueError("only posted payments can be reversed")
        if await session.scalar(text("SELECT 1 FROM payment_reversals WHERE tenant_id=:t AND payment_id=:p"),{"t":tenant_id,"p":payment_id}):
            raise ValueError("payment has already been reversed")
        period=await session.scalar(text("SELECT id FROM accounting_periods WHERE tenant_id=:t AND starts_on<=:d AND ends_on>=:d AND status='OPEN' ORDER BY starts_on DESC LIMIT 1"),{"t":tenant_id,"d":date.today()})
        if not period: raise ValueError("no open accounting period for reversal")
        treasury=(await session.execute(text("SELECT ledger_account_id,currency FROM treasury_accounts WHERE tenant_id=:t AND id=:a FOR UPDATE"),{"t":tenant_id,"a":payment["treasury_account_id"]})).mappings().one_or_none()
        if not treasury or not treasury["ledger_account_id"]: raise ValueError("treasury ledger account is not configured")
        operation=payment["direction"]
        profile=(await session.execute(text("""
          SELECT debit_account_id,credit_account_id FROM accounting_posting_profiles
          WHERE tenant_id=:t AND company_id IS NOT DISTINCT FROM :c AND operation=:o AND currency=:cur AND active
            AND effective_from<=:d AND (effective_to IS NULL OR effective_to>=:d)
          ORDER BY effective_from DESC LIMIT 1
        """),{"t":tenant_id,"c":payment["company_id"],"o":operation,"cur":payment["currency"],"d":date.today()})).mappings().one_or_none()
        if not profile: raise ValueError("payment posting profile is not configured")
        if payment["direction"]=="RECEIPT": debit,credit=profile["credit_account_id"],treasury["ledger_account_id"]
        else: debit,credit=treasury["ledger_account_id"],profile["debit_account_id"]
        if not debit or not credit: raise ValueError("reversal posting accounts are incomplete")
        lines=[{"account_id":str(debit),"debit":str(payment["amount"]),"credit":"0","currency":payment["currency"],"description":"Payment reversal"},
               {"account_id":str(credit),"debit":"0","credit":str(payment["amount"]),"currency":payment["currency"],"description":"Payment reversal"}]
        entry=await session.scalar(text("SELECT post_journal(:t,:p,:d,:desc,'PAYMENT_REVERSAL',:src,:u,CAST(:lines AS jsonb))"),{"t":tenant_id,"p":period,"d":date.today(),"desc":reason,"src":payment_id,"u":actor_id,"lines":json.dumps(lines)})
        reversal=await session.scalar(text("""
          INSERT INTO payments(tenant_id,company_id,partner_id,direction,payment_date,amount,currency,treasury_account_id,external_reference,status,idempotency_key,journal_entry_id,created_by,posted_at)
          VALUES(:t,:c,:p,:dir,:d,:a,:cur,:ta,:ext,'REVERSED',:key,:j,:u,now()) RETURNING id
        """),{"t":tenant_id,"c":payment["company_id"],"p":payment["partner_id"],"dir":"DISBURSEMENT" if payment["direction"]=="RECEIPT" else "RECEIPT","d":date.today(),"a":payment["amount"],"cur":payment["currency"],"ta":payment["treasury_account_id"],"ext":payment["external_reference"],"key":f"REV-{payment_id}","j":entry,"u":actor_id})
        await session.execute(text("""
          INSERT INTO treasury_movements(tenant_id,treasury_account_id,movement_date,direction,amount,currency,reference,payment_id,journal_entry_id,status)
          VALUES(:t,:a,:d,:md,:amt,:cur,:ref,:p,:j,'POSTED')
        """), {"t":tenant_id,"a":payment["treasury_account_id"],"d":date.today(),"md":"OUT" if payment["direction"]=="RECEIPT" else "IN","amt":payment["amount"],"cur":payment["currency"],"ref":f"REVERSAL:{payment_id}","p":reversal,"j":entry})
        await session.execute(text("SELECT reverse_payment_allocations(:t,:p,:r)"),{"t":tenant_id,"p":payment_id,"r":reversal})
        await session.execute(text("UPDATE payments SET status='REVERSED',reversed_at=now() WHERE tenant_id=:t AND id=:p"),{"t":tenant_id,"p":payment_id})
        await session.execute(text("INSERT INTO payment_reversals(tenant_id,payment_id,reversal_payment_id,reason,created_by) VALUES(:t,:p,:r,:reason,:u)"),{"t":tenant_id,"p":payment_id,"r":reversal,"reason":reason,"u":actor_id})
        return UUID(str(reversal))
