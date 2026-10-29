"""Concurrency-safe allocation of posted payments against open AR/AP balances."""
from __future__ import annotations
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class PaymentService:
    async def allocate(self, session: AsyncSession, tenant_id: UUID, payment_id: UUID,
                       receivable_id: UUID, amount: Decimal) -> None:
        if amount <= 0: raise ValueError("allocation amount must be positive")
        payment=(await session.execute(text("SELECT amount,currency,status FROM payments WHERE tenant_id=:t AND id=:p FOR UPDATE"),{"t":tenant_id,"p":payment_id})).mappings().one_or_none()
        if not payment: raise ValueError("payment not found")
        if payment["status"] != "POSTED": raise ValueError("only posted payments can be allocated")
        rp=(await session.execute(text("SELECT outstanding_amount,currency,status FROM receivable_payable WHERE tenant_id=:t AND id=:r FOR UPDATE"),{"t":tenant_id,"r":receivable_id})).mappings().one_or_none()
        if not rp: raise ValueError("receivable/payable not found")
        if rp["status"] in {"SETTLED","CANCELLED"}: raise ValueError("receivable/payable is not open")
        if rp["currency"] != payment["currency"]: raise ValueError("currency mismatch")
        if amount > Decimal(str(rp["outstanding_amount"])): raise ValueError("allocation exceeds outstanding balance")
        allocated=Decimal(str(await session.scalar(text("SELECT COALESCE(sum(amount),0) FROM payment_allocations WHERE tenant_id=:t AND payment_id=:p"),{"t":tenant_id,"p":payment_id})))
        if allocated+amount > Decimal(str(payment["amount"])): raise ValueError("allocations exceed payment amount")
        await session.execute(text("INSERT INTO payment_allocations(tenant_id,payment_id,receivable_payable_id,amount) VALUES(:t,:p,:r,:a)"),{"t":tenant_id,"p":payment_id,"r":receivable_id,"a":amount})
        remaining=Decimal(str(rp["outstanding_amount"]))-amount
        await session.execute(text("UPDATE receivable_payable SET outstanding_amount=:o,status=:s WHERE tenant_id=:t AND id=:r"),{"o":remaining,"s":"SETTLED" if remaining==0 else "PARTIALLY_SETTLED","t":tenant_id,"r":receivable_id})
