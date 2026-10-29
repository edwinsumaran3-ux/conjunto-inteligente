"""Application services for executable accounting workflows.

The database functions are authoritative for concurrency, tenant isolation and
journal creation. This layer validates command shape and exposes typed boundaries.
"""
from __future__ import annotations
from decimal import Decimal
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AccountingWorkflowService:
    async def run_depreciation(self, session: AsyncSession, tenant_id: UUID, company_id: UUID,
                               year: int, month: int, actor_id: UUID) -> UUID:
        if not 1 <= month <= 12:
            raise ValueError("month must be between 1 and 12")
        result = await session.scalar(text("SELECT run_asset_depreciation(:t,:c,:y,:m,:a)"),
            {"t": tenant_id, "c": company_id, "y": year, "m": month, "a": actor_id})
        if result is None:
            raise RuntimeError("depreciation workflow returned no run id")
        return UUID(str(result))

    async def post_provision_movement(self, session: AsyncSession, tenant_id: UUID, provision_id: UUID,
                                      movement_type: str, amount: Decimal, actor_id: UUID) -> UUID:
        if amount <= 0:
            raise ValueError("amount must be positive")
        result = await session.scalar(text(
            "SELECT post_provision_movement(:t,:p,:kind,:amount,:a)"),
            {"t": tenant_id, "p": provision_id, "kind": movement_type,
             "amount": amount, "a": actor_id})
        if result is None:
            raise RuntimeError("provision workflow returned no movement id")
        return UUID(str(result))

    async def execute_annual_close(self, session: AsyncSession, tenant_id: UUID, company_id: UUID,
                                   year: int, actor_id: UUID) -> UUID:
        result = await session.scalar(text("SELECT execute_annual_close(:t,:c,:y,:a)"),
            {"t": tenant_id, "c": company_id, "y": year, "a": actor_id})
        if result is None:
            raise RuntimeError("annual close workflow returned no run id")
        return UUID(str(result))
