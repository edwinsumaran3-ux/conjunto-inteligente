import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.app.modules.edge_transport import api


class FakeSession:
    def __init__(self, scoped_count=1, budget_allowed=1):
        self.scoped_count = scoped_count
        self.budget_allowed = budget_allowed
        self.statements = []

    async def execute(self, statement, parameters):
        self.statements.append((str(statement), parameters))

    async def scalar(self, statement, parameters):
        self.statements.append((str(statement), parameters))
        if "edge_telemetry_ingest_limits" in str(statement):
            return self.budget_allowed
        return self.scoped_count


def _batch(gateway_id, point_id, sequence=12):
    return api.GatewayTelemetryBatch(
        gateway_id=gateway_id,
        nonce="nonce-value-123456",
        sequence=sequence,
        samples=[{
            "point_id": point_id,
            "value": 21.5,
            "unit": "degC",
            "observed_at": datetime.now(timezone.utc),
            "source": "untrusted-source",
            "source_message_id": "sample-1",
            "sequence": 1234,
            "metadata": {
                "data_origin": "simulated",
                "gateway_id": "untrusted-gateway",
                "hardware_connected": False,
            },
        }],
    )


def test_gateway_batch_overrides_declared_provenance_and_reuses_batch_ingestion(monkeypatch):
    tenant_id, gateway_id, node_id, point_id = (uuid4() for _ in range(4))
    batch = _batch(gateway_id, point_id)
    session = FakeSession()
    captured = {}

    async def verify(*args):
        captured["verification"] = args
        return {"node_id": node_id, "gateway_status": "registered"}

    async def ingest(telemetry, auth, db_session):
        captured["telemetry"] = telemetry
        captured["auth"] = auth
        assert db_session is session
        return {"status": "accepted", "accepted": 1, "duplicates": 0}

    monkeypatch.setattr(api, "_verify_gateway", verify)
    monkeypatch.setattr(api, "_ingest_operational_batch", ingest)

    result = asyncio.run(api.ingest_gateway_telemetry(batch, "signature", tenant_id, session))

    sample = captured["telemetry"].samples[0]
    assert captured["verification"][0:4] == (
        tenant_id, gateway_id, batch.nonce, batch.sequence,
    )
    assert captured["auth"].tenant_id == str(tenant_id)
    assert sample.source == f"edge-gateway:{gateway_id}"
    assert sample.source_message_id == f"{gateway_id}:sample-1"
    assert sample.sequence == 1234
    assert sample.metadata == {
        "data_origin": "physical",
        "gateway_id": str(gateway_id),
        "hardware_connected": True,
    }
    assert result["accepted"] == 1
    assert result["data_origin"] == "physical"
    assert any("WITH RECURSIVE node_scope" in sql for sql, _ in session.statements)
    budget = next(
        parameters for sql, parameters in session.statements
        if "edge_telemetry_ingest_limits" in sql
    )
    assert budget["tenant_id"] == tenant_id
    assert budget["gateway_id"] == gateway_id
    assert budget["sample_count"] == 1
    assert budget["max_requests"] == api._GATEWAY_TELEMETRY_REQUESTS_PER_MINUTE
    assert budget["max_samples"] == api._GATEWAY_TELEMETRY_SAMPLES_PER_MINUTE


def test_gateway_batch_rejects_points_outside_assigned_subtree(monkeypatch):
    tenant_id, gateway_id, node_id, point_id = (uuid4() for _ in range(4))
    session = FakeSession(scoped_count=0)

    async def verify(*args):
        assert args[1] == gateway_id
        return {"node_id": node_id, "gateway_status": "registered"}

    async def ingest(*args):
        pytest.fail(f"out-of-scope point reached telemetry persistence: {args!r}")

    monkeypatch.setattr(api, "_verify_gateway", verify)
    monkeypatch.setattr(api, "_ingest_operational_batch", ingest)

    with pytest.raises(HTTPException) as error:
        asyncio.run(api.ingest_gateway_telemetry(
            _batch(gateway_id, point_id), "signature", tenant_id, session,
        ))

    assert error.value.status_code == 403
    assert error.value.detail == "EDGE_GATEWAY_POINT_OUTSIDE_ASSIGNED_NODE_SCOPE"


def test_gateway_telemetry_sequences_fit_postgres_bigint():
    batch = _batch(uuid4(), uuid4())
    with pytest.raises(ValueError):
        api.GatewayTelemetryBatch.model_validate({
            **batch.model_dump(mode="json"),
            "samples": [{
                **batch.samples[0].model_dump(mode="json"),
                "sequence": 2**63,
            }],
        })


def test_gateway_telemetry_budget_returns_retryable_429(monkeypatch):
    tenant_id, gateway_id, node_id, point_id = (uuid4() for _ in range(4))
    session = FakeSession(budget_allowed=None)

    async def verify(*args):
        assert args[1] == gateway_id
        return {"node_id": node_id, "gateway_status": "registered"}

    async def ingest(*args):
        pytest.fail(f"over-limit batch reached telemetry persistence: {args!r}")

    monkeypatch.setattr(api, "_verify_gateway", verify)
    monkeypatch.setattr(api, "_ingest_operational_batch", ingest)

    with pytest.raises(HTTPException) as error:
        asyncio.run(api.ingest_gateway_telemetry(
            _batch(gateway_id, point_id), "signature", tenant_id, session,
        ))

    assert error.value.status_code == 429
    assert error.value.detail["code"] == "EDGE_TELEMETRY_RATE_LIMITED"
    assert error.value.headers["Retry-After"] == "60"
    assert any("WITH RECURSIVE node_scope" in sql for sql, _ in session.statements)


@pytest.mark.parametrize("raw", ["", "0", "-1", "not-an-integer", "100001"])
def test_gateway_telemetry_limits_reject_invalid_configuration(monkeypatch, raw):
    monkeypatch.setenv("EDGE_TEST_LIMIT", raw)
    with pytest.raises(RuntimeError):
        api._positive_limit("EDGE_TEST_LIMIT", 120, 100_000)


def test_gateway_authentication_keeps_watermark_and_bounded_retention(monkeypatch):
    tenant_id, gateway_id = uuid4(), uuid4()
    gateway_row = {
        "status": "active",
        "public_key": "public-key",
        "node_id": uuid4(),
        "gateway_status": "registered",
        "last_sequence": 50,
    }

    class ReplaySession:
        def __init__(self):
            self.statements = []

        async def execute(self, statement, parameters):
            sql = str(statement)
            self.statements.append((sql, parameters))
            if "SELECT c.public_key" in sql:
                return type("Result", (), {
                    "mappings": lambda _self: type("Mappings", (), {
                        "first": lambda _self: gateway_row,
                    })(),
                })()
            if "SELECT sequence FROM edge_transport_replays" in sql:
                return type("Result", (), {
                    "scalar_one_or_none": lambda _self: None,
                })()
            if "SELECT COALESCE(MAX(sequence)" in sql:
                return type("Result", (), {
                    "scalar_one": lambda _self: 48,
                })()
            return None

    session = ReplaySession()
    monkeypatch.setattr(api, "verify_ed25519", lambda *_args: True)

    verified = asyncio.run(api._verify_gateway(
        tenant_id, gateway_id, "nonce-value-123456", 51, {"ok": True},
        "signature", session,
    ))

    assert verified is gateway_row
    assert any(
        "UPDATE edge_devices SET last_sequence=:q" in sql
        and parameters["q"] == 51
        for sql, parameters in session.statements
    )
    cleanup_sql, cleanup_parameters = next(
        (sql, parameters) for sql, parameters in session.statements
        if "DELETE FROM edge_transport_replays" in sql
    )
    assert "LIMIT 1000" in cleanup_sql
    assert "interval '30 days'" in cleanup_sql
    assert cleanup_parameters == {"t": tenant_id, "d": gateway_id}
