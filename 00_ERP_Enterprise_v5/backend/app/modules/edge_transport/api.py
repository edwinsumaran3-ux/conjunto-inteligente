from __future__ import annotations

import json
import os
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session
from backend.app.db.session import get_session
from backend.app.modules.digital_twin.api.router import (
    TelemetryBatchIn,
    TelemetrySampleIn,
    _ingest_operational_batch,
)
from .service import payload_hash, verify_ed25519

router = APIRouter(prefix="/edge-transport", tags=["edge-transport"])
_MAX_TRANSPORT_SEQUENCE = 2**63 - 1


def _positive_limit(variable: str, default: int, maximum: int) -> int:
    raw = os.getenv(variable, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{variable} must be an integer") from exc
    if not 1 <= value <= maximum:
        raise RuntimeError(f"{variable} must be between 1 and {maximum}")
    return value


_GATEWAY_TELEMETRY_REQUESTS_PER_MINUTE = _positive_limit(
    "EDGE_TELEMETRY_MAX_REQUESTS_PER_MINUTE", 120, 100_000,
)
_GATEWAY_TELEMETRY_SAMPLES_PER_MINUTE = _positive_limit(
    "EDGE_TELEMETRY_MAX_SAMPLES_PER_MINUTE", 10_000, 1_000_000,
)


class TransportEvent(BaseModel):
    event_id: str = Field(min_length=1, max_length=160)
    gateway_id: UUID
    nonce: str = Field(min_length=16, max_length=160)
    sequence: int = Field(ge=1, le=_MAX_TRANSPORT_SEQUENCE)
    occurred_at_ms: int = Field(ge=0)
    event_type: str = Field(min_length=1, max_length=120)
    device_id: UUID | None = None
    payload: dict = Field(default_factory=dict)


class CommandAck(BaseModel):
    command_id: UUID
    sequence: int = Field(ge=1, le=_MAX_TRANSPORT_SEQUENCE)
    status: str = Field(pattern="^(acknowledged|completed|failed)$")
    result: dict = Field(default_factory=dict)
    nonce: str = Field(min_length=16, max_length=160)


class Heartbeat(BaseModel):
    gateway_id: UUID
    sequence: int = Field(ge=1, le=_MAX_TRANSPORT_SEQUENCE)
    firmware_version: str | None = None
    safety_state: str = Field(pattern="^(armed|safe|kill_switch|quarantined)$")
    health: dict = Field(default_factory=dict)
    connectivity: dict = Field(default_factory=dict)
    nonce: str = Field(min_length=16, max_length=160)


class GatewayTelemetrySample(TelemetrySampleIn):
    sequence: int | None = Field(default=None, ge=0, le=_MAX_TRANSPORT_SEQUENCE)


class GatewayTelemetryBatch(BaseModel):
    gateway_id: UUID
    nonce: str = Field(min_length=16, max_length=160)
    sequence: int = Field(ge=1, le=_MAX_TRANSPORT_SEQUENCE)
    samples: list[GatewayTelemetrySample] = Field(min_length=1, max_length=500)


async def _enforce_gateway_telemetry_budget(
    session,
    tenant_id: UUID,
    gateway_id: UUID,
    sample_count: int,
) -> None:
    admitted = await session.scalar(text("""
        WITH current_window AS (
            SELECT date_trunc('minute', clock_timestamp()) AS window_started_at
        )
        INSERT INTO edge_telemetry_ingest_limits(
            tenant_id, device_id, window_started_at, request_count, sample_count
        )
        SELECT :tenant_id, :gateway_id, current_window.window_started_at, 1,
               CAST(:sample_count AS integer)
        FROM current_window
        WHERE CAST(:sample_count AS integer)<=CAST(:max_samples AS integer)
        ON CONFLICT(tenant_id, device_id) DO UPDATE SET
            window_started_at=EXCLUDED.window_started_at,
            request_count=CASE
                WHEN edge_telemetry_ingest_limits.window_started_at=EXCLUDED.window_started_at
                    THEN edge_telemetry_ingest_limits.request_count+1
                ELSE 1
            END,
            sample_count=CASE
                WHEN edge_telemetry_ingest_limits.window_started_at=EXCLUDED.window_started_at
                    THEN edge_telemetry_ingest_limits.sample_count+EXCLUDED.sample_count
                ELSE EXCLUDED.sample_count
            END,
            updated_at=clock_timestamp()
        WHERE CAST(:sample_count AS integer)<=CAST(:max_samples AS integer)
          AND (
                edge_telemetry_ingest_limits.window_started_at<>EXCLUDED.window_started_at
                OR (
                edge_telemetry_ingest_limits.request_count<CAST(:max_requests AS integer)
                AND edge_telemetry_ingest_limits.sample_count+EXCLUDED.sample_count
                    <=CAST(:max_samples AS integer)
                )
          )
        RETURNING request_count
    """), {
        "tenant_id": tenant_id,
        "gateway_id": gateway_id,
        "sample_count": sample_count,
        "max_requests": _GATEWAY_TELEMETRY_REQUESTS_PER_MINUTE,
        "max_samples": _GATEWAY_TELEMETRY_SAMPLES_PER_MINUTE,
    })
    if admitted is None:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "EDGE_TELEMETRY_RATE_LIMITED",
                "window_seconds": 60,
                "max_requests": _GATEWAY_TELEMETRY_REQUESTS_PER_MINUTE,
                "max_samples": _GATEWAY_TELEMETRY_SAMPLES_PER_MINUTE,
            },
            headers={"Retry-After": "60"},
        )


def _device_key(row):
    if not row:
        raise HTTPException(401, "EDGE_GATEWAY_UNKNOWN")
    if row["status"] in {"revoked", "expired"}:
        raise HTTPException(401, "EDGE_CREDENTIAL_REVOKED")
    return row["public_key"]


async def _verify_gateway(
    tenant_id: UUID,
    gateway_id: UUID,
    nonce: str,
    sequence: int,
    payload: dict,
    signature: str,
    s,
):
    row = (await s.execute(text("""
        SELECT c.public_key, c.status, d.node_id, d.status AS gateway_status,
               d.last_sequence
        FROM edge_device_credentials c
        JOIN edge_devices d ON d.device_id=c.device_id AND d.tenant_id=c.tenant_id
        WHERE c.tenant_id=:t AND c.device_id=:d
          AND c.status='active' AND c.algorithm='ed25519'
          AND (c.valid_from IS NULL OR c.valid_from<=CURRENT_DATE)
        ORDER BY c.valid_from DESC LIMIT 1
        FOR UPDATE OF c,d
    """), {"t":tenant_id,"d": gateway_id})).mappings().first()
    public_key = _device_key(row)
    envelope = {"gateway_id": str(gateway_id), "nonce": nonce, "sequence": sequence, "payload": payload}
    if not verify_ed25519(envelope, signature, public_key):
        raise HTTPException(401, "EDGE_SIGNATURE_INVALID")

    replay = (await s.execute(text("""
        SELECT sequence FROM edge_transport_replays
        WHERE tenant_id=:t AND device_id=:d AND nonce=:n
    """), {"t":tenant_id,"d": gateway_id, "n": nonce})).scalar_one_or_none()
    if replay is not None:
        raise HTTPException(409, "EDGE_REPLAY_NONCE")
    replay_watermark = (await s.execute(text("""
        SELECT COALESCE(MAX(sequence),0) FROM edge_transport_replays
        WHERE tenant_id=:t AND device_id=:d
    """), {"t":tenant_id,"d": gateway_id})).scalar_one()
    last_sequence = max(int(row["last_sequence"] or 0), int(replay_watermark))
    if sequence <= last_sequence:
        raise HTTPException(409, "EDGE_REPLAY_SEQUENCE")
    await s.execute(text("""
        INSERT INTO edge_transport_replays(tenant_id,device_id,nonce,sequence,payload_hash)
        VALUES(:t,:d,:n,:q,:h)
    """), {"t":tenant_id,"d": gateway_id, "n": nonce, "q": sequence, "h": payload_hash(payload)})
    await s.execute(text("""
        UPDATE edge_devices SET last_sequence=:q,updated_at=now()
        WHERE tenant_id=:t AND device_id=:d
    """), {"t": tenant_id, "d": gateway_id, "q": sequence})
    await s.execute(text("""
        DELETE FROM edge_transport_replays
        WHERE ctid IN (
            SELECT ctid FROM edge_transport_replays
            WHERE tenant_id=:t AND device_id=:d
              AND created_at<clock_timestamp()-interval '30 days'
            ORDER BY created_at, row_id
            LIMIT 1000
        )
    """), {"t": tenant_id, "d": gateway_id})
    return row


@router.post("/events", status_code=202)
async def ingest_event(
    event: TransportEvent,
    x_edge_signature: str = Header(..., alias="X-Edge-Signature"),
    x_edge_tenant_id: UUID = Header(..., alias="X-Edge-Tenant-Id"),
    s=Depends(get_session),
):
    await s.execute(text("SELECT set_config('app.current_tenant_id', :t, true)"), {"t": str(x_edge_tenant_id)})
    await _verify_gateway(x_edge_tenant_id,event.gateway_id,event.nonce,event.sequence,event.model_dump(mode="json"),x_edge_signature,s)
    tenant = x_edge_tenant_id
    device_id = event.device_id or event.gateway_id
    await s.execute(text("""
        INSERT INTO edge_event_spool(tenant_id,device_id,event_key,sequence,event_type,payload,payload_hash,status)
        VALUES(:t,:d,:k,:q,:e,CAST(:p AS jsonb),:h,'pending')
        ON CONFLICT(tenant_id,device_id,sequence) DO NOTHING
    """), {"t": tenant, "d": device_id, "k": event.event_id, "q": event.sequence,
          "e": event.event_type, "p": json.dumps(event.payload), "h": payload_hash(event.payload)})

    if event.event_type == "edge.command_ack":
        command_id = event.payload.get("command_id")
        status = event.payload.get("status")
        if command_id and status in {"acknowledged", "completed", "failed"}:
            await s.execute(text("""
                UPDATE edge_commands SET status=:st, acknowledged_at=CASE WHEN :st='acknowledged' THEN now() ELSE acknowledged_at END,
                    completed_at=CASE WHEN :st IN ('completed','failed') THEN now() ELSE completed_at END, result=CAST(:r AS jsonb)
                WHERE tenant_id=:t AND command_id=:c AND device_id=:d
            """), {"st": status, "r": json.dumps(event.payload.get("result", {})), "t": tenant,
                  "c": command_id, "d": event.gateway_id})
    await s.execute(text("UPDATE edge_devices SET status='online', last_heartbeat_at=now(), updated_at=now() WHERE tenant_id=:t AND device_id=:d"), {"t": tenant, "d": event.gateway_id})
    await s.commit()
    return {"accepted": True, "event_id": event.event_id}


@router.post("/heartbeat", status_code=202)
async def heartbeat(
    hb: Heartbeat,
    x_edge_signature: str = Header(..., alias="X-Edge-Signature"),
    x_edge_tenant_id: UUID = Header(..., alias="X-Edge-Tenant-Id"),
    s=Depends(get_session),
):
    await s.execute(text("SELECT set_config('app.current_tenant_id', :t, true)"), {"t": str(x_edge_tenant_id)})
    await _verify_gateway(x_edge_tenant_id,hb.gateway_id,hb.nonce,hb.sequence,hb.model_dump(mode="json"),x_edge_signature,s)
    tenant = x_edge_tenant_id
    await s.execute(text("""
        INSERT INTO edge_heartbeats(tenant_id,device_id,sequence,firmware_version,connectivity,health,safety_state,signature)
        VALUES(:t,:d,:q,:f,CAST(:c AS jsonb),CAST(:h AS jsonb),:s,:sig)
    """), {"t": tenant, "d": hb.gateway_id, "q": hb.sequence, "f": hb.firmware_version,
          "c": json.dumps(hb.connectivity), "h": json.dumps(hb.health), "s": hb.safety_state, "sig": x_edge_signature})
    await s.execute(text("UPDATE edge_devices SET status='online', safety_state=:s, last_heartbeat_at=now(), last_sequence=GREATEST(last_sequence,:q), updated_at=now() WHERE tenant_id=:t AND device_id=:d"),
                    {"t": tenant, "d": hb.gateway_id, "s": hb.safety_state, "q": hb.sequence})
    await s.commit()
    return {"accepted": True, "gateway_id": str(hb.gateway_id)}


@router.post("/telemetry/batch", status_code=202)
async def ingest_gateway_telemetry(
    batch: GatewayTelemetryBatch,
    x_edge_signature: str = Header(..., alias="X-Edge-Signature"),
    x_edge_tenant_id: UUID = Header(..., alias="X-Edge-Tenant-Id"),
    s=Depends(get_session),
):
    await s.execute(
        text("SELECT set_config('app.current_tenant_id', :t, true)"),
        {"t": str(x_edge_tenant_id)},
    )
    gateway = await _verify_gateway(
        x_edge_tenant_id,
        batch.gateway_id,
        batch.nonce,
        batch.sequence,
        batch.model_dump(mode="json"),
        x_edge_signature,
        s,
    )
    if gateway["gateway_status"] in {
        "disabled", "revoked", "expired", "retired", "quarantined",
    }:
        raise HTTPException(403,"EDGE_GATEWAY_DISABLED")
    if gateway["node_id"] is None:
        raise HTTPException(403,"EDGE_GATEWAY_NODE_SCOPE_REQUIRED")

    tenant_point_ids = list(dict.fromkeys(sample.point_id for sample in batch.samples))
    parameters = {"t": x_edge_tenant_id, "root": gateway["node_id"]}
    placeholders = []
    for index, point_id in enumerate(tenant_point_ids):
        key = f"point_{index}"
        parameters[key] = point_id
        placeholders.append(f":{key}")
    scoped_count=await s.scalar(text(f"""
        WITH RECURSIVE node_scope(id) AS (
            SELECT id FROM twin_nodes WHERE tenant_id=:t AND id=:root
            UNION
            SELECT child.id FROM twin_nodes child
            JOIN node_scope parent ON child.parent_id=parent.id
            WHERE child.tenant_id=:t
        )
        SELECT count(DISTINCT p.id)
        FROM twin_points p
        JOIN node_scope scope ON scope.id=p.node_id
        WHERE p.tenant_id=:t AND p.id IN ({', '.join(placeholders)})
    """),parameters)
    if scoped_count != len(tenant_point_ids):
        raise HTTPException(403, "EDGE_GATEWAY_POINT_OUTSIDE_ASSIGNED_NODE_SCOPE")

    source = f"edge-gateway:{batch.gateway_id}"
    message_prefix = f"{batch.gateway_id}:"
    samples = []
    for index, sample in enumerate(batch.samples):
        message_id = sample.source_message_id
        if not message_id:
            raise HTTPException(422, "EDGE_SAMPLE_SOURCE_MESSAGE_ID_REQUIRED")
        prefixed_message_id = f"{message_prefix}{message_id}"
        if len(prefixed_message_id) > 240:
            raise HTTPException(422, "EDGE_SAMPLE_SOURCE_MESSAGE_ID_TOO_LONG")
        metadata = dict(sample.metadata)
        metadata.update({
            "data_origin": "physical",
            "gateway_id": str(batch.gateway_id),
            "hardware_connected": True,
        })
        samples.append(sample.model_copy(update={
            "source": source,
            "source_message_id": prefixed_message_id,
            "metadata": metadata,
        }))

    await _enforce_gateway_telemetry_budget(
        s, x_edge_tenant_id, batch.gateway_id, len(samples),
    )
    result = await _ingest_operational_batch(
        TelemetryBatchIn(samples=samples),
        AuthContext(str(x_edge_tenant_id), str(batch.gateway_id)),
        s,
    )
    await s.execute(text("""
        UPDATE edge_devices
        SET status='online',last_heartbeat_at=now(),
            last_sequence=GREATEST(last_sequence,:q),updated_at=now()
        WHERE tenant_id=:t AND device_id=:d
    """), {"q": batch.sequence, "t": x_edge_tenant_id, "d": batch.gateway_id})
    return {
        **result,
        "gateway_id": str(batch.gateway_id),
        "data_origin": "physical",
        "hardware_connected": True,
    }



@router.get("/commands/{gateway_id}/signed")
async def pull_signed_commands(
    gateway_id: UUID,
    limit: int = Query(default=10, ge=1, le=50),
    x_edge_signature: str = Header(..., alias="X-Edge-Signature"),
    x_edge_tenant_id: UUID = Header(..., alias="X-Edge-Tenant-Id"),
    x_edge_nonce: str = Header(..., alias="X-Edge-Nonce"),
    x_edge_sequence: int = Header(..., alias="X-Edge-Sequence", ge=1, le=_MAX_TRANSPORT_SEQUENCE),
    s=Depends(get_session),
):
    await s.execute(text("SELECT set_config('app.current_tenant_id', :t, true)"), {"t": str(x_edge_tenant_id)})
    request_payload={"gateway_id":str(gateway_id),"nonce":x_edge_nonce,"sequence":x_edge_sequence,"limit":limit}
    await _verify_gateway(x_edge_tenant_id,gateway_id,x_edge_nonce,x_edge_sequence,request_payload,x_edge_signature,s)
    tenant=x_edge_tenant_id
    rows=(await s.execute(text("""
        SELECT command_id,envelope,payload,signature,sequence,expires_at,status
        FROM edge_commands WHERE tenant_id=:t AND device_id=:d AND status IN ('issued','leased')
          AND expires_at>now() AND (status='issued' OR lease_expires_at<=now())
        ORDER BY sequence LIMIT :l FOR UPDATE SKIP LOCKED
    """),{"t":tenant,"d":gateway_id,"l":limit})).mappings().all()
    commands=[]
    for row in rows:
        await s.execute(text("UPDATE edge_commands SET status='leased',lease_id=:l,lease_expires_at=now()+interval '30 seconds' WHERE tenant_id=:t AND command_id=:c"),{"l":uuid4(),"t":tenant,"c":row["command_id"]})
        commands.append(dict(row))
    await s.commit()
    return {"commands":commands}

@router.get("/commands/{gateway_id}")
async def pull_commands(
    gateway_id: UUID,
    limit: int = Query(default=10, ge=1, le=50),
    auth: AuthContext = Depends(get_auth_context),
    s=Depends(get_tenant_session),
):
    # Operator-only bootstrap/pull is retained for administration. Physical gateways should use
    # the separate device-authenticated transport endpoint once provisioned.
    if not ({"operator", "admin", "administrator", "security_admin"} & set(auth.roles)):
        raise HTTPException(403, "OPERATOR_ROLE_REQUIRED")
    rows = (await s.execute(text("""
        SELECT command_id, command_type, sequence, nonce, expires_at, payload, envelope, signature
        FROM edge_commands WHERE tenant_id=:t AND device_id=:d AND status='issued' AND expires_at>now()
        ORDER BY sequence LIMIT :l FOR UPDATE SKIP LOCKED
    """), {"t": UUID(auth.tenant_id), "d": gateway_id, "l": limit})).mappings().all()
    result=[]
    for row in rows:
        await s.execute(text("UPDATE edge_commands SET status='leased', lease_id=:l, lease_expires_at=now()+interval '30 seconds' WHERE tenant_id=:t AND command_id=:c"),
                        {"l": uuid4(), "t": UUID(auth.tenant_id), "c": row["command_id"]})
        result.append(dict(row))
    await s.commit()
    return {"commands": result}
