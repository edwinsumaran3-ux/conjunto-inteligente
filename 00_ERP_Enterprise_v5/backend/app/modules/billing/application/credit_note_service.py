"""Credit/debit note relationship rules for Colombian financial documents."""
from __future__ import annotations
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AdjustmentNoteService:
    async def create_link(self, session: AsyncSession, tenant_id: UUID, note_id: UUID, original_id: UUID, note_type: str) -> None:
        note_type = note_type.upper()
        if note_type not in {"CREDIT_NOTE", "DEBIT_NOTE"}:
            raise ValueError("invalid adjustment note type")
        if note_id == original_id:
            raise ValueError("adjustment note cannot reference itself")
        rows = (await session.execute(text("""
            SELECT id, document_type, lifecycle_status, currency
            FROM financial_documents
            WHERE tenant_id=:t AND id IN (:n,:o)
            FOR UPDATE
        """), {"t": tenant_id, "n": note_id, "o": original_id})).mappings().all()
        if len(rows) != 2:
            raise ValueError("note and original document must exist in the same tenant")
        by_id = {r["id"]: r for r in rows}
        original = by_id[original_id]
        if original["document_type"] != "INVOICE" or original["lifecycle_status"] not in {"VALIDATED", "VOIDED"}:
            raise ValueError("original invoice must be validated or voided before adjustment")
        await session.execute(text("""
            UPDATE financial_documents
            SET original_document_id=:o, document_type=:dt
            WHERE tenant_id=:t AND id=:n AND lifecycle_status='DRAFT'
        """), {"t": tenant_id, "n": note_id, "o": original_id, "dt": note_type})
