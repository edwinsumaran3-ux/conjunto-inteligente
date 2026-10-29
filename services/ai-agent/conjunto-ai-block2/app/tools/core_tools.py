from __future__ import annotations
from typing import Any
from app.integrations.core_client import CoreClient


class CoreTools:
    def __init__(self, client: CoreClient):
        self.client = client

    async def get_asset_history(self, asset_id: str) -> dict[str, Any]:
        if not asset_id:
            raise ValueError("asset_id is required")
        return await self.client.get_asset_history(asset_id)

    async def search_area(self, keywords: list[str]) -> dict[str, Any]:
        normalized = [item.strip() for item in keywords if item and item.strip()]
        if not normalized:
            raise ValueError("At least one non-empty keyword is required")
        return await self.client.get_area_by_keywords(normalized)
