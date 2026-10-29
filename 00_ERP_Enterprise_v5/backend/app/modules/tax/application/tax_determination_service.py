"""Version-aware tax determination backed by tenant-configured tax rules."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class TaxDeterminationService:
    async def determine(self, session: AsyncSession, tenant_id: UUID, company_id: UUID | None,
                        effective_date: date, base: Decimal, tax_code: str) -> Decimal:
        if base < 0: raise ValueError("tax base cannot be negative")
        rule=(await session.execute(text("""
          SELECT rate,rounding_scale FROM tax_rules
          WHERE tenant_id=:t AND company_id IS NOT DISTINCT FROM :c AND code=:code AND active
            AND effective_from<=:d AND (effective_to IS NULL OR effective_to>=:d)
          ORDER BY effective_from DESC LIMIT 1
        """),{"t":tenant_id,"c":company_id,"code":tax_code,"d":effective_date})).mappings().one_or_none()
        if not rule: raise ValueError(f"tax rule not configured: {tax_code}")
        scale=int(rule["rounding_scale"])
        quantum=Decimal(1).scaleb(-scale)
        return (base*Decimal(str(rule["rate"])) / Decimal('100')).quantize(quantum,ROUND_HALF_UP)
