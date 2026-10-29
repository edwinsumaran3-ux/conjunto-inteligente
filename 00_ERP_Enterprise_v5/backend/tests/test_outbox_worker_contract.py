from uuid import UUID

import pytest

from backend.app.core.outbox_worker import CLAIM, _tenant_uuid, dispatch_batch


@pytest.mark.parametrize("value", ["", "not-a-uuid", None])
def test_tenant_must_be_uuid(value):
    with pytest.raises(ValueError, match="tenant_id"):
        _tenant_uuid(value)


def test_claim_matches_canonical_outbox_contract():
    sql = str(CLAIM).lower()
    assert "tenant_id = :tenant_id" in sql
    assert "event_type" in sql
    assert "topic" not in sql
    assert "status = 'pending'" in sql
    assert "status = 'processing'" in sql
    assert "for update skip locked" in sql


@pytest.mark.asyncio
async def test_invalid_batch_size_fails_before_database_access():
    with pytest.raises(ValueError, match="batch_size"):
        await dispatch_batch(None, "00000000-0000-0000-0000-000000000001", None, batch_size=0)


@pytest.mark.asyncio
async def test_invalid_attempt_limit_fails_before_database_access():
    with pytest.raises(ValueError, match="max_attempts"):
        await dispatch_batch(None, "00000000-0000-0000-0000-000000000001", None, max_attempts=0)


def test_tenant_id_normalizes_to_uuid():
    expected = UUID("00000000-0000-0000-0000-000000000001")
    assert _tenant_uuid(str(expected)) == expected
