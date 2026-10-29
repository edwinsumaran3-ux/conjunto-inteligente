"""Issue and post validated financial documents as one transactional process."""
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from backend.app.modules.accounting.application.posting_service import AccountingPostingService


class InvoiceIssueService:
    def __init__(self, posting: AccountingPostingService | None = None):
        self.posting = posting or AccountingPostingService()

    async def issue(self, session: AsyncSession, tenant_id: UUID, document_id: UUID, actor_id: UUID) -> UUID:
        row = (await session.execute(text("""
            SELECT lifecycle_status,dian_status,journal_entry_id
            FROM financial_documents WHERE tenant_id=:t AND id=:d FOR UPDATE
        """), {"t": tenant_id, "d": document_id})).mappings().one_or_none()
        if not row: raise ValueError("financial document not found")
        if row["dian_status"] != "VALIDATED":
            raise ValueError("document cannot be posted until DIAN validation is recorded")
        if row["lifecycle_status"] == "VALIDATED" and row["journal_entry_id"]:
            return UUID(str(row["journal_entry_id"]))
        if row["lifecycle_status"] != "VALIDATED":
            raise ValueError("document lifecycle must be VALIDATED before posting")
        return await self.posting.post_document(session, tenant_id, document_id, actor_id)
