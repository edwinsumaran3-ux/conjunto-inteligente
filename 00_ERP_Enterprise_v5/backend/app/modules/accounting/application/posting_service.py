"""Atomic posting orchestration for business documents and treasury movements."""
from __future__ import annotations
import json
from datetime import date
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class PostingConfigurationError(RuntimeError):
    """Raised when a company has not configured the required ledger mapping."""


class AccountingPostingService:
    async def _profile(self, session: AsyncSession, tenant_id: UUID, company_id: UUID | None,
                       operation: str, currency: str, at: date):
        row = (await session.execute(text("""
            SELECT * FROM accounting_posting_profiles
            WHERE tenant_id=:t AND company_id IS NOT DISTINCT FROM :c
              AND operation=:o AND currency=:cur AND active
              AND effective_from<=:d AND (effective_to IS NULL OR effective_to>=:d)
            ORDER BY effective_from DESC LIMIT 1
        """), {"t": tenant_id, "c": company_id, "o": operation,
              "cur": currency.upper(), "d": at})).mappings().one_or_none()
        if not row:
            raise PostingConfigurationError(f"posting profile not configured: {operation}/{currency}")
        return row

    async def post_document(self, session: AsyncSession, tenant_id: UUID, document_id: UUID,
                            actor_id: UUID) -> UUID:
        doc = (await session.execute(text("""
            SELECT d.*, p.id AS period_id FROM financial_documents d
            JOIN accounting_periods p ON p.tenant_id=d.tenant_id AND d.issue_date BETWEEN p.starts_on AND p.ends_on
                AND p.status='OPEN'
            WHERE d.tenant_id=:t AND d.id=:d ORDER BY p.starts_on DESC LIMIT 1 FOR UPDATE OF d
        """), {"t": tenant_id, "d": document_id})).mappings().one_or_none()
        if not doc:
            raise ValueError("financial document or accounting period not found")
        if doc["lifecycle_status"] != "VALIDATED":
            raise ValueError("financial document must be externally validated before posting")
        if doc["dian_status"] not in {"VALIDATED", "NOT_REQUIRED"}:
            raise ValueError("financial document does not have an admissible DIAN state")
        if doc["journal_entry_id"]:
            return UUID(str(doc["journal_entry_id"]))
        operation = "SALES_INVOICE" if doc["direction"] == "AR" and doc["document_type"] == "INVOICE" else "PURCHASE_INVOICE"
        profile = await self._profile(session, tenant_id, doc["company_id"], operation, doc["currency"], doc["issue_date"])
        lines = (await session.execute(text("""
            SELECT line_no,description,line_subtotal,tax_amount,account_id
            FROM financial_document_lines WHERE tenant_id=:t AND financial_document_id=:d ORDER BY line_no
        """), {"t": tenant_id, "d": document_id})).mappings().all()
        if not lines:
            raise ValueError("financial document has no lines")
        jlines: list[dict[str,str]] = []
        if operation == "SALES_INVOICE":
            if not profile["debit_account_id"]: raise PostingConfigurationError("AR account is not configured")
            jlines.append({"account_id": str(profile["debit_account_id"]), "debit": str(doc["total_amount"]), "credit": "0", "currency": doc["currency"], "description": "Accounts receivable"})
            for line in lines:
                jlines.append({"account_id": str(line["account_id"]), "debit": "0", "credit": str(line["line_subtotal"]), "currency": doc["currency"], "description": line["description"]})
            if Decimal(str(doc["tax_amount"])) > 0:
                if not profile["tax_credit_account_id"]: raise PostingConfigurationError("output tax account is not configured")
                jlines.append({"account_id": str(profile["tax_credit_account_id"]), "debit": "0", "credit": str(doc["tax_amount"]), "currency": doc["currency"], "description": "Output tax"})
        else:
            if not profile["credit_account_id"]: raise PostingConfigurationError("AP account is not configured")
            jlines.append({"account_id": str(profile["credit_account_id"]), "debit": "0", "credit": str(doc["total_amount"]), "currency": doc["currency"], "description": "Accounts payable"})
            for line in lines:
                jlines.append({"account_id": str(line["account_id"]), "debit": str(line["line_subtotal"]), "credit": "0", "currency": doc["currency"], "description": line["description"]})
            if Decimal(str(doc["tax_amount"])) > 0:
                if not profile["tax_debit_account_id"]: raise PostingConfigurationError("input tax account is not configured")
                jlines.append({"account_id": str(profile["tax_debit_account_id"]), "debit": str(doc["tax_amount"]), "credit": "0", "currency": doc["currency"], "description": "Input tax"})
        entry = await session.scalar(text("""
            SELECT post_journal(:t,:p,:d,:desc,'FINANCIAL_DOCUMENT',:source,:u,CAST(:lines AS jsonb))
        """), {"t": tenant_id, "p": doc["period_id"], "d": doc["issue_date"],
              "desc": f"{doc['document_type']} {doc['series']}-{doc['number']}", "source": document_id,
              "u": actor_id, "lines": json.dumps(jlines)})
        updated = await session.execute(text("""
            UPDATE financial_documents SET journal_entry_id=:j, issued_at=COALESCE(issued_at,now())
            WHERE tenant_id=:t AND id=:d AND journal_entry_id IS NULL
            RETURNING id
        """), {"j": entry, "t": tenant_id, "d": document_id})
        if updated.scalar_one_or_none() is None:
            raise RuntimeError("financial document posting race detected")

        # AR/AP is a consequence of a posted document, never of a draft. The
        # uniqueness constraint makes this operation idempotent under retries.
        await session.execute(text("""
            INSERT INTO receivable_payable
              (tenant_id,financial_document_id,original_amount,outstanding_amount,currency,status)
            VALUES (:t,:d,:a,:a,:c,'OPEN')
            ON CONFLICT (tenant_id,financial_document_id) DO NOTHING
        """), {"t": tenant_id, "d": document_id, "a": doc["total_amount"], "c": doc["currency"]})
        return UUID(str(entry))
