from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class FinancialReportingService:
    """Read-only financial statements derived from posted immutable journals."""

    async def trial_balance(self, session: AsyncSession, tenant_id: UUID,
                            company_id: UUID, as_of: date) -> list[dict]:
        rows = (await session.execute(text("""
            SELECT ca.code, ca.name, ca.kind, ca.normal_side,
                   COALESCE(SUM(l.debit),0) AS debit,
                   COALESCE(SUM(l.credit),0) AS credit,
                   COALESCE(SUM(l.debit-l.credit),0) AS net
            FROM chart_accounts ca
            LEFT JOIN (
              journal_lines l
              JOIN journal_entries e
                ON e.tenant_id=l.tenant_id AND e.id=l.journal_entry_id
               AND e.company_id=:c AND e.status='POSTED' AND e.entry_date<=:d
            ) ON l.tenant_id=ca.tenant_id AND l.account_id=ca.id
            WHERE ca.tenant_id=:t
            GROUP BY ca.code,ca.name,ca.kind,ca.normal_side
            ORDER BY ca.code
        """), {"t": tenant_id, "c": company_id, "d": as_of})).mappings().all()
        return [dict(r) for r in rows]

    async def income_statement(self, session: AsyncSession, tenant_id: UUID,
                               company_id: UUID, start: date, end: date) -> dict:
        if end < start:
            raise ValueError("end date cannot precede start date")
        rows = (await session.execute(text("""
            SELECT ca.kind,
                   COALESCE(SUM(l.debit),0) AS debit,
                   COALESCE(SUM(l.credit),0) AS credit
            FROM chart_accounts ca
            JOIN journal_lines l ON l.tenant_id=ca.tenant_id AND l.account_id=ca.id
            JOIN journal_entries e ON e.tenant_id=l.tenant_id AND e.id=l.journal_entry_id
            WHERE e.company_id=:c AND e.status='POSTED' AND e.entry_date BETWEEN :s AND :e
              AND ca.tenant_id=:t AND ca.kind IN ('REVENUE','EXPENSE')
            GROUP BY ca.kind
        """), {"t": tenant_id, "c": company_id, "s": start, "e": end})).mappings().all()
        values = {r["kind"]: (Decimal(str(r["credit"])) - Decimal(str(r["debit"]))) for r in rows}
        revenue = values.get("REVENUE", Decimal("0"))
        expense = -values.get("EXPENSE", Decimal("0"))
        return {"revenue": revenue, "expense": expense, "net_income": revenue + expense}
