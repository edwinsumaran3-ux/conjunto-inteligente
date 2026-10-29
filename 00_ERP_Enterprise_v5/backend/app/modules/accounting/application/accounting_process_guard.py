"""Deterministic accounting process guard.

AI may explain or recommend accounting treatment, but this guard is the
machine-enforced authorization boundary for posting-critical invariants.
"""
from __future__ import annotations
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AccountingProcessGuard:
    async def assert_period_open(self, session: AsyncSession, tenant_id: UUID, period_id: UUID) -> None:
        status = await session.scalar(text("""
            SELECT status FROM accounting_periods
            WHERE tenant_id=:t AND id=:p FOR UPDATE
        """), {"t": tenant_id, "p": period_id})
        if status is None:
            raise ValueError("accounting period not found")
        if status != "OPEN":
            raise ValueError("accounting period is not open")

    async def assert_document_postable(self, session: AsyncSession, tenant_id: UUID, document_id: UUID) -> dict:
        row = (await session.execute(text("""
            SELECT id, company_id, document_type, direction, lifecycle_status,
                   issue_date, currency, subtotal, tax_amount, withholding_amount,
                   total_amount, balance_amount, journal_entry_id
            FROM financial_documents
            WHERE tenant_id=:t AND id=:d FOR UPDATE
        """), {"t": tenant_id, "d": document_id})).mappings().one_or_none()
        if not row:
            raise ValueError("financial document not found")
        if row["lifecycle_status"] != "VALIDATED":
            raise ValueError("only VALIDATED financial documents can be posted")
        if row["journal_entry_id"] is not None:
            raise ValueError("financial document is already posted")
        return dict(row)
