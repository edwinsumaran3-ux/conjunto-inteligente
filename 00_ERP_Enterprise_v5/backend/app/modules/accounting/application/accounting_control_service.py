from __future__ import annotations

from datetime import date
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AccountingControlService:
    """Independent pre-close controls. A report never authorizes a posting."""

    async def run_controls(self, session: AsyncSession, tenant_id: UUID,
                           company_id: UUID, period_id: UUID) -> list[dict]:
        checks = [
            ("UNBALANCED_POSTED_JOURNAL", """
                SELECT COUNT(*) FROM (
                  SELECT e.id FROM journal_entries e
                  JOIN journal_lines l ON l.tenant_id=e.tenant_id AND l.journal_entry_id=e.id
                  WHERE e.tenant_id=:t AND e.company_id=:c AND e.period_id=:p AND e.status='POSTED'
                  GROUP BY e.id HAVING SUM(l.debit) <> SUM(l.credit)
                ) x"""),
            ("POSTED_WITHOUT_LINES", """
                SELECT COUNT(*) FROM journal_entries e
                WHERE e.tenant_id=:t AND e.company_id=:c AND e.period_id=:p AND e.status='POSTED'
                  AND NOT EXISTS (SELECT 1 FROM journal_lines l WHERE l.tenant_id=e.tenant_id AND l.journal_entry_id=e.id)"""),
            ("OPEN_PERIOD", """
                SELECT COUNT(*) FROM accounting_periods
                WHERE tenant_id=:t AND id=:p AND status='OPEN'"""),
        ]
        result: list[dict] = []
        for code, sql in checks:
            value = int(await session.scalar(text(sql), {"t": tenant_id, "c": company_id, "p": period_id}) or 0)
            passed = value == 0 if code != "OPEN_PERIOD" else value == 1
            result.append({"code": code, "passed": passed, "observed": value})
        return result
