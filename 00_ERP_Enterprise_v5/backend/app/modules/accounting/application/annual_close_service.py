from __future__ import annotations
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

class AnnualCloseService:
    """Application boundary for annual close; database function is authoritative."""
    async def complete(self, session: AsyncSession, tenant_id: UUID, company_id: UUID, fiscal_year: int, actor_id: UUID) -> UUID:
        result = await session.scalar(text("SELECT complete_annual_close(:t,:c,:y,:a)"), {"t": tenant_id, "c": company_id, "y": fiscal_year, "a": actor_id})
        if result is None:
            raise RuntimeError("annual close did not return a run identifier")
        return result
