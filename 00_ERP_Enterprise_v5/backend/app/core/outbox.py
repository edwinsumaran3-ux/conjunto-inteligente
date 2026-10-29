"""Transactional outbox helper used by domain APIs."""
import json
from uuid import uuid4
from sqlalchemy import text

async def enqueue(session, tenant_id, event_type, aggregate_type, aggregate_id, payload, producer="api"):
    """Insert an outbox event in the caller's transaction.

    Requires the `outbox_events` table from the digital-twin migration. Fails
    loudly if the schema is missing so callers cannot mistake an event for a
    durable delivery.
    """
    event_id = uuid4()
    await session.execute(
        text("""INSERT INTO outbox_events
        (id, tenant_id, event_type, aggregate_type, aggregate_id, payload, producer, status, created_at)
        VALUES (:id, :tenant_id, :event_type, :aggregate_type, :aggregate_id,
                CAST(:payload AS jsonb), :producer, 'pending', now())"""),
        {"id": event_id, "tenant_id": tenant_id, "event_type": event_type,
         "aggregate_type": aggregate_type, "aggregate_id": str(aggregate_id),
         "payload": json.dumps(payload, default=str), "producer": producer},
    )
    return str(event_id)
