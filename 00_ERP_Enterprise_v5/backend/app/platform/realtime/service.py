"""Tenant-scoped replay API for persisted realtime events."""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from typing import Any
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

@dataclass(frozen=True)
class RealtimeEvent:
    event_id: UUID
    sequence: int
    topic: str
    correlation_id: str | None
    payload: Any
    payload_sha256: str

def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

async def publish(session: AsyncSession, *, tenant_id: UUID, topic: str, payload: Any, correlation_id: str | None = None) -> UUID:
    """Productor de eventos: persiste en realtime_events con el hash que replay() verifica. Participa en la transacción del llamador (si falla, no se publica)."""
    if not topic or len(topic) < 5 or len(topic) > 160: raise ValueError("invalid realtime topic")
    from uuid import uuid4
    eid = uuid4(); body = json.loads(json.dumps(payload, default=str))
    await session.execute(text("""INSERT INTO realtime_events(event_id,tenant_id,topic,correlation_id,payload,payload_sha256)
        VALUES(:e,:t,:tp,:c,CAST(:p AS jsonb),:h)"""), {"e": eid, "t": tenant_id, "tp": topic, "c": correlation_id, "p": json.dumps(body, default=str), "h": canonical_sha256(body)})
    return eid

class RealtimeService:
    async def replay(self, session: AsyncSession, *, tenant_id: UUID, actor_id: UUID,
                     topic: str, after_sequence: int = 0, limit: int = 100) -> list[RealtimeEvent]:
        if not topic or len(topic) > 160 or after_sequence < 0 or not 1 <= limit <= 500:
            raise ValueError("invalid replay parameters")
        rows = (await session.execute(text("""SELECT event_id, sequence, topic, correlation_id, payload, payload_sha256
          FROM realtime_events WHERE tenant_id=:tenant AND topic=:topic AND sequence>:after
          ORDER BY sequence ASC LIMIT :limit"""),
          {"tenant": tenant_id, "topic": topic, "after": after_sequence, "limit": limit})).mappings().all()
        events=[]
        for row in rows:
            payload = row["payload"]
            if isinstance(payload, str): payload=json.loads(payload)
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
            stored = str(row["payload_sha256"])
            if digest != stored:
                raise RuntimeError(f"realtime event payload integrity check failed for {row['event_id']}")
            events.append(RealtimeEvent(row["event_id"], int(row["sequence"]), str(row["topic"]),
                         str(row["correlation_id"]) if row["correlation_id"] is not None else None, payload, stored))
        return events
