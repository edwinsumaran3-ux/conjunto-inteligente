"""Append-only application audit events. Caller controls transaction boundaries."""
from __future__ import annotations
import json
from uuid import UUID, uuid4
from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def append_audit_event(session: AsyncSession, *, tenant_id: UUID, actor_id: UUID | None,
                             action: str, entity_type: str, entity_id: str,
                             before: Any = None, after: Any = None) -> UUID:
    if not action or len(action) > 160 or not entity_type or len(entity_type) > 120:
        raise ValueError("action and entity_type are required and bounded")
    event_id = uuid4()
    await session.execute(text("""INSERT INTO audit_log
      (id, tenant_id, actor_id, action, entity_type, entity_id, before_state, after_state, created_at)
      VALUES (:id,:tenant,:actor,:action,:entity_type,:entity_id,CAST(:before AS jsonb),CAST(:after AS jsonb),now())"""),
      {"id": event_id, "tenant": tenant_id, "actor": actor_id, "action": action, "entity_type": entity_type,
       "entity_id": str(entity_id), "before": json.dumps(before, default=str) if before is not None else None,
       "after": json.dumps(after, default=str) if after is not None else None})
    return event_id
