import pytest
from app.integrations.core_client import CoreClient, CoreUnavailableError


@pytest.mark.asyncio
async def test_core_unavailable():
    client = CoreClient(base_url="http://127.0.0.1:59999", timeout=0.05, max_retries=1)
    with pytest.raises(CoreUnavailableError):
        await client.get_asset_history("asset-001")
