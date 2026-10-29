"""PostgreSQL-backed tenant-scoped idempotency helpers.

The caller owns the surrounding transaction. `reserve` never commits, allowing
business mutation and the stored response to commit atomically.
"""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.exceptions import IdempotencyConflict

@dataclass(frozen=True)
class IdempotencyResult:
    status: str
    response_body: dict[str, Any] | None = None
    response_status: int | None = None

def fingerprint(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

async def reserve(session: AsyncSession, tenant_id: UUID, key: str, route: str, request_hash: str) -> IdempotencyResult:
    if not isinstance(key, str) or not key.strip() or len(key) > 200:
        raise ValueError("a non-empty idempotency key of at most 200 characters is required")
    if not isinstance(route, str) or not route or len(route) > 240:
        raise ValueError("route must be a non-empty string of at most 240 characters")
    if len(request_hash) != 64 or any(c not in "0123456789abcdef" for c in request_hash.lower()):
        raise ValueError("request_hash must be a SHA-256 hex digest")
    result = await session.execute(text("""INSERT INTO idempotency_records
      (tenant_id, idempotency_key, route, request_hash, status, response_status, response_body, created_at, expires_at)
      VALUES (:tenant, :key, :route, :hash, 'in_progress', NULL, NULL, now(), now() + interval '24 hours')
      ON CONFLICT (tenant_id, idempotency_key, route) DO UPDATE
        SET request_hash=EXCLUDED.request_hash, status='in_progress', response_status=NULL,
            response_body=NULL, created_at=now(), expires_at=now() + interval '24 hours'
        WHERE idempotency_records.expires_at < now()
      RETURNING status, response_status, response_body"""), {"tenant": tenant_id, "key": key, "route": route, "hash": request_hash})
    row = result.mappings().first()
    if row is not None:
        # Reserva NUEVA (o reactivada por expiración): el llamador es dueño de la ejecución.
        # Antes devolvía 'in_progress', que los 5 servicios interpretan como "otra petición en curso" -> la primera llamada siempre fallaba.
        return IdempotencyResult("reserved", None, None)
    row = (await session.execute(text("""SELECT request_hash, status, response_status, response_body
       FROM idempotency_records WHERE tenant_id=:tenant AND idempotency_key=:key AND route=:route FOR UPDATE"""),
       {"tenant": tenant_id, "key": key, "route": route})).mappings().one_or_none()
    if row is None:
        raise RuntimeError("idempotency reservation disappeared; retry the transaction")
    if row["request_hash"] != request_hash:
        raise IdempotencyConflict("idempotency key was already used with a different request")
    return IdempotencyResult(str(row["status"]), row["response_body"], row["response_status"])

async def complete(session: AsyncSession, tenant_id: UUID, key: str, route: str, status_code: int, response_body: dict[str, Any]) -> None:
    if not 100 <= int(status_code) <= 599:
        raise ValueError("status_code must be an HTTP status")
    body = json.dumps(response_body, ensure_ascii=False, separators=(",", ":"), default=str)
    result = await session.execute(text("""UPDATE idempotency_records SET status='completed', response_status=:status,
      response_body=CAST(:body AS jsonb), completed_at=now() WHERE tenant_id=:tenant AND idempotency_key=:key
      AND route=:route AND status='in_progress'"""), {"status": status_code, "body": body, "tenant": tenant_id, "key": key, "route": route})
    if result.rowcount != 1:
        raise RuntimeError("idempotency reservation was not in progress")
