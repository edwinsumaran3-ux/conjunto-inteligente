from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from backend.app.api.deps import AuthContext
from backend.app.modules.digital_twin.api.router import list_nodes


@pytest.mark.asyncio
async def test_list_nodes_is_tenant_scoped_and_paginated():
    tenant_id = str(uuid4())
    row = {"id": str(uuid4()), "name": "Bomba B1", "parent_name": "Torre 1"}
    result = MagicMock()
    result.mappings.return_value.all.return_value = [row]
    session = MagicMock()
    session.scalar = AsyncMock(return_value=1)
    session.execute = AsyncMock(return_value=result)

    response = await list_nodes(
        limit=25,
        offset=10,
        search="Bomba",
        node_type="ifcpump",
        auth=AuthContext(tenant_id, str(uuid4())),
        session=session,
    )

    assert response == {"items": [row], "total": 1, "limit": 25, "offset": 10}
    count_sql = str(session.scalar.await_args.args[0])
    select_sql = str(session.execute.await_args.args[0])
    params = session.execute.await_args.args[1]
    assert "n.tenant_id=:t" in count_sql
    assert "n.tenant_id=:t" in select_sql
    assert params == {
        "t": UUID(tenant_id),
        "limit": 25,
        "offset": 10,
        "search": "%Bomba%",
        "node_type": "ifcpump",
    }


@pytest.mark.asyncio
async def test_list_nodes_returns_empty_page_for_tenant_without_assets():
    session = MagicMock()
    session.scalar = AsyncMock(return_value=0)
    result = MagicMock()
    result.mappings.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)

    response = await list_nodes(
        limit=100,
        offset=0,
        search=None,
        node_type=None,
        auth=AuthContext(str(uuid4()), str(uuid4())),
        session=session,
    )

    assert response == {"items": [], "total": 0, "limit": 100, "offset": 0}
