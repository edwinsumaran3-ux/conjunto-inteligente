"""Tenant-scoped, at-least-once dispatcher for the ERP outbox schema.

The caller owns the database engine/session factory and publisher transport.
Consumers MUST deduplicate by event id: a crash after publish and before the
PUBLISHED update can cause a redelivery.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

Publisher = Callable[[dict[str, Any]], Awaitable[None]]

# Keep this SQL aligned with 001_outbox_events.sql + 002_outbox_dispatcher.sql.
CLAIM = text("""WITH picked AS (
    SELECT id
      FROM outbox_events
     WHERE tenant_id = :tenant_id
       AND ((status = 'pending' AND available_at <= CURRENT_TIMESTAMP)
         OR (status = 'processing' AND locked_at < CURRENT_TIMESTAMP - INTERVAL '2 minutes'))
     ORDER BY created_at, id
     FOR UPDATE SKIP LOCKED
     LIMIT :batch_size
)
UPDATE outbox_events AS e
   SET status = 'processing', locked_at = CURRENT_TIMESTAMP, attempts = e.attempts + 1
  FROM picked
 WHERE e.id = picked.id AND e.tenant_id = :tenant_id
RETURNING e.id, e.tenant_id, e.event_type, e.aggregate_type, e.aggregate_id,
          e.payload, e.producer, e.attempts""")


def _tenant_uuid(tenant_id: str | UUID) -> UUID:
    try:
        return tenant_id if isinstance(tenant_id, UUID) else UUID(str(tenant_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("tenant_id must be a valid UUID") from exc


async def _set_tenant(session: AsyncSession, tenant_id: UUID) -> None:
    # Transaction-local RLS context; do not leave tenant context on a pooled connection.
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


async def dispatch_batch(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str | UUID,
    publish: Publisher,
    *,
    batch_size: int = 100,
    max_attempts: int = 8,
) -> int:
    """Dispatch one tenant's due events; at-least-once delivery, tenant scoped."""
    tenant = _tenant_uuid(tenant_id)
    if not 1 <= batch_size <= 1000:
        raise ValueError("batch_size must be 1..1000")
    if not 1 <= max_attempts <= 100:
        raise ValueError("max_attempts must be 1..100")
    if not callable(publish):
        raise ValueError("publish must be callable")

    async with session_factory() as session:
        async with session.begin():
            await _set_tenant(session, tenant)
            rows = (await session.execute(CLAIM, {"tenant_id": tenant, "batch_size": batch_size})).mappings().all()
            claimed = [dict(row) for row in rows]

    for event in claimed:
        event["id"] = str(event["id"])
        event["tenant_id"] = str(event["tenant_id"])
        if isinstance(event["payload"], str):
            event["payload"] = json.loads(event["payload"])
        try:
            await publish(event)
        except Exception as exc:  # persist retry/dead status; don't kill the whole batch
            attempts = int(event["attempts"])
            delay_seconds = min(300, 2 ** min(attempts, 8))
            async with session_factory() as session:
                async with session.begin():
                    await _set_tenant(session, tenant)
                    await session.execute(
                        text("""UPDATE outbox_events
                                  SET status = :status,
                                      available_at = CURRENT_TIMESTAMP + (:delay * INTERVAL '1 second'),
                                      locked_at = NULL,
                                      last_error = :error
                                WHERE id = :id AND tenant_id = :tenant_id AND status = 'processing'"""),
                        {"status": "failed" if attempts >= max_attempts else "pending",
                         "delay": delay_seconds, "error": str(exc)[:2000],
                         "id": event["id"], "tenant_id": tenant},
                    )
        else:
            async with session_factory() as session:
                async with session.begin():
                    await _set_tenant(session, tenant)
                    await session.execute(
                        text("""UPDATE outbox_events
                                  SET status = 'published', published_at = CURRENT_TIMESTAMP,
                                      locked_at = NULL, last_error = NULL
                                WHERE id = :id AND tenant_id = :tenant_id AND status = 'processing'"""),
                        {"id": event["id"], "tenant_id": tenant},
                    )
    return len(claimed)


async def run_forever(
    session_factory: async_sessionmaker[AsyncSession],
    tenant_id: str | UUID,
    publish: Publisher,
    *,
    poll_seconds: float = 1.0,
) -> None:
    """Poll one tenant. Schedule one worker per authorized tenant."""
    _tenant_uuid(tenant_id)
    if not 0.1 <= poll_seconds <= 60:
        raise ValueError("poll_seconds must be 0.1..60")
    while True:
        count = await dispatch_batch(session_factory, tenant_id, publish)
        if count == 0:
            await asyncio.sleep(poll_seconds)
