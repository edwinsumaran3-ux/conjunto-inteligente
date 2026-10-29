from __future__ import annotations
import asyncio
from typing import Any
import httpx
from app.core.config import get_settings


class CoreClientError(RuntimeError):
    pass


class CoreUnavailableError(CoreClientError):
    pass


class CoreClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.core_base_url).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.core_timeout_seconds
        self.max_retries = max(
            0, max_retries if max_retries is not None else settings.core_max_retries
        )

    async def _request(
        self, method: str, path: str, *, json: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(method, url, json=json)
                if 200 <= response.status_code < 300:
                    if not response.content:
                        return {}
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise CoreClientError(
                            "Core returned a non-JSON success response"
                        ) from exc
                if response.status_code in {408, 425, 429, 500, 502, 503, 504}:
                    last_error = CoreUnavailableError(
                        f"Core returned HTTP {response.status_code}"
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(min(2**attempt, 5))
                        continue
                    raise last_error
                raise CoreClientError(
                    f"Core returned HTTP {response.status_code}: {response.text[:500]}"
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(min(2**attempt, 5))
                    continue
        raise CoreUnavailableError(
            f"Core unavailable after {self.max_retries + 1} attempts"
        ) from last_error

    async def get_asset_history(self, asset_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/assets/{asset_id}/history")

    async def get_area_by_keywords(self, keywords: list[str]) -> dict[str, Any]:
        return await self._request(
            "POST", "/api/v1/areas/search", json={"keywords": keywords}
        )

    async def create_procurement_request(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._request("POST", "/api/v1/procurement/requests", json=payload)

    async def health(self) -> bool:
        try:
            await self._request("GET", "/health")
            return True
        except CoreClientError:
            return False
