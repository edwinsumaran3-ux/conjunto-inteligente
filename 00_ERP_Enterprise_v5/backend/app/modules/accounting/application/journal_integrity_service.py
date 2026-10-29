from __future__ import annotations
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

class JournalIntegrityService:
    """Verifies the immutable journal hash chain under tenant context."""
    async def verify(self, session: AsyncSession, tenant_id: UUID) -> None:
        await session.execute(text("SELECT validate_journal_hash_chain(:t)"), {"t": tenant_id})
