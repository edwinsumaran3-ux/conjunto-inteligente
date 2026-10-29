from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.api.deps import AuthContext
from backend.app.modules.digital_twin.api.router import (
    TelemetryBatchIn,
    TelemetrySampleIn,
    _ingest_operational_batch,
    _telemetry_payload_hash,
)


def _result(rows=()):
    result = MagicMock()
    result.mappings.return_value.all.return_value = list(rows)
    return result


def _sample(point_id, message_id, value, *, unit="C", quality="GOOD"):
    return TelemetrySampleIn(
        point_id=point_id,
        value=value,
        unit=unit,
        observed_at=datetime.now(timezone.utc),
        source="test-adapter",
        source_message_id=message_id,
        source_quality=quality,
    )


@pytest.mark.asyncio
async def test_batch_inserts_samples_in_one_statement_and_updates_point_once():
    tenant_id, point_id, device_id = uuid4(), uuid4(), uuid4()
    messages = [f"msg-{index}" for index in range(3)]
    samples = TelemetryBatchIn(samples=[
        _sample(point_id, message_id, 20 + index)
        for index, message_id in enumerate(messages)
    ])
    inserted = [
        {"source_message_id": message_id, "id": index + 10}
        for index, message_id in enumerate(messages)
    ]
    hashes = {
        sample.source_message_id: _telemetry_payload_hash(sample, sample.observed_at)
        for sample in samples.samples
    }
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[
        _result([{
            "id": point_id, "node_id": uuid4(), "device_id": device_id,
            "canonical_unit": "C", "engineering_min": 0.0, "engineering_max": 50.0,
            "stale_after_seconds": 300,
        }]),
        _result(),
        _result(inserted),
        _result([{"source_message_id": message_id, "payload_hash": hashes[message_id]} for message_id in messages]),
        MagicMock(),
        MagicMock(),
    ])
    response = await _ingest_operational_batch(
        samples,
        AuthContext(str(tenant_id), str(uuid4())),
        session,
    )

    assert response["received"] == 3
    assert response["accepted"] == 3
    assert response["duplicates"] == 0
    assert [sample["status"] for sample in response["samples"]] == ["accepted"] * 3
    sql_calls = [str(call.args[0]) for call in session.execute.await_args_list]
    insert_statements = [sql for sql in sql_calls if "INSERT INTO twin_telemetry_samples" in sql]
    state_statements = [sql for sql in sql_calls if "INSERT INTO twin_point_states" in sql]
    assert len(insert_statements) == 1
    assert len(state_statements) == 1
    assert "WHERE tenant_id=:t" in sql_calls[0]
    assert "ON CONFLICT (tenant_id,source_message_id)" in insert_statements[0]


@pytest.mark.asyncio
async def test_batch_rejects_reused_message_id_with_different_payload_before_writes():
    tenant_id, point_id = uuid4(), uuid4()
    session = MagicMock()
    session.execute = AsyncMock(return_value=_result([{
        "id": point_id, "node_id": uuid4(), "device_id": None,
        "canonical_unit": "C", "engineering_min": 0.0, "engineering_max": 50.0,
        "stale_after_seconds": 300,
    }]))
    batch = TelemetryBatchIn(samples=[
        _sample(point_id, "same-id", 20),
        _sample(point_id, "same-id", 21),
    ])

    with pytest.raises(HTTPException) as failure:
        await _ingest_operational_batch(
            batch, AuthContext(str(tenant_id), str(uuid4())), session
        )

    assert failure.value.status_code == 409
    assert failure.value.detail == "BATCH_MESSAGE_ID_REUSED_WITH_DIFFERENT_PAYLOAD"
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_batch_validates_all_samples_before_persisting_any():
    tenant_id, point_id = uuid4(), uuid4()
    session = MagicMock()
    session.execute = AsyncMock(return_value=_result([{
        "id": point_id, "node_id": uuid4(), "device_id": None,
        "canonical_unit": "C", "engineering_min": 0.0, "engineering_max": 50.0,
        "stale_after_seconds": 300,
    }]))
    batch = TelemetryBatchIn(samples=[
        _sample(point_id, "valid", 20),
        _sample(point_id, "invalid-conversion", 10, unit="psi"),
    ])

    with pytest.raises(HTTPException) as failure:
        await _ingest_operational_batch(
            batch, AuthContext(str(tenant_id), str(uuid4())), session
        )

    assert failure.value.status_code == 422
    assert "UNSUPPORTED_UNIT_CONVERSION" in failure.value.detail
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_batch_requires_idempotency_keys():
    batch = TelemetryBatchIn(samples=[
        _sample(uuid4(), None, 20),
    ])
    session = MagicMock()
    session.execute = AsyncMock()

    with pytest.raises(HTTPException) as failure:
        await _ingest_operational_batch(
            batch, AuthContext(str(uuid4()), str(uuid4())), session
        )

    assert failure.value.status_code == 422
    assert failure.value.detail == "BATCH_SAMPLE_SOURCE_MESSAGE_ID_REQUIRED"
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_exact_replay_is_reported_without_insert_or_state_writes():
    tenant_id, point_id = uuid4(), uuid4()
    sample = _sample(point_id, "already-stored", 20)
    sample_hash = _telemetry_payload_hash(sample, sample.observed_at)
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[
        _result([{
            "id": point_id, "node_id": uuid4(), "device_id": None,
            "canonical_unit": "C", "engineering_min": 0.0, "engineering_max": 50.0,
            "stale_after_seconds": 300,
        }]),
        _result([{"source_message_id": "already-stored", "payload_hash": sample_hash}]),
    ])

    response = await _ingest_operational_batch(
        TelemetryBatchIn(samples=[sample]),
        AuthContext(str(tenant_id), str(uuid4())),
        session,
    )

    assert response["status"] == "duplicate"
    assert response["accepted"] == 0
    assert response["samples"][0]["status"] == "duplicate"
    assert session.execute.await_count == 2


def test_batch_and_sample_models_reject_oversized_and_non_finite_inputs():
    with pytest.raises(ValidationError):
        _sample(uuid4(), "non-finite", float("inf"))

    sample = _sample(uuid4(), "message", 1)
    with pytest.raises(ValidationError):
        TelemetryBatchIn(samples=[sample] * 501)
