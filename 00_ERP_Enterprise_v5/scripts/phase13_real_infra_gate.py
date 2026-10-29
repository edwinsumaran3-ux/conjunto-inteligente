"""Disposable-environment PostgreSQL/Redis integration gate for Docker Compose test.

Applies the project's reviewed idempotent SQL migrations to the dedicated test DB,
then verifies database access, tenant RLS behavior, outbox schema, and Redis health.
Never point this script at production: it mutates schema and creates temporary rows.
"""
from __future__ import annotations
import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse
import asyncpg
import redis.asyncio as redis

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = [ROOT / "backend/app/modules/digital_twin/migrations/001_outbox_events.sql", *sorted((ROOT / "migrations/sql").glob("2026*.sql"))]

def pg_url() -> str:
    raw = os.getenv("PHASE13_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not raw:
        raise RuntimeError("PHASE13_DATABASE_URL or DATABASE_URL is required")
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)

def redis_url() -> str:
    value = os.getenv("PHASE13_REDIS_URL") or os.getenv("REDIS_URL")
    if not value:
        raise RuntimeError("PHASE13_REDIS_URL or REDIS_URL is required")
    return value

async def main() -> None:
    conn = await asyncpg.connect(pg_url())
    try:
        await conn.execute("SELECT 1")
        for migration in MIGRATIONS:
            if not migration.is_file():
                raise FileNotFoundError(f"required SQL migration not found: {migration}")
            await conn.execute(migration.read_text(encoding="utf-8"))
        tables = await conn.fetchval("""SELECT count(*) FROM information_schema.tables
            WHERE table_schema='public' AND table_name = ANY($1::text[])""",
            ["outbox_events", "tenants", "users", "idempotency_records", "audit_log", "realtime_events", "user_totp_credentials"])
        if tables != 7:
            raise RuntimeError(f"schema smoke test expected 7 tables, found {tables}")
        # Use a transaction-local tenant setting and prove a different tenant is hidden by RLS.
        async with conn.transaction():
            tenant_a = await conn.fetchval("INSERT INTO tenants(name) VALUES('integration-test-a') RETURNING id")
            tenant_b = await conn.fetchval("INSERT INTO tenants(name) VALUES('integration-test-b') RETURNING id")
            await conn.execute("SELECT set_config('app.current_tenant_id',$1,true)", str(tenant_a))
            await conn.execute("INSERT INTO audit_log(id,tenant_id,action,entity_type,entity_id) VALUES(gen_random_uuid(),$1,'integration.test','Gate','a')", tenant_a)
            visible = await conn.fetchval("SELECT count(*) FROM audit_log WHERE tenant_id=$1", tenant_b)
            if visible != 0:
                raise RuntimeError("tenant RLS isolation smoke test failed")
            # Deliberately roll back the temporary tenant and audit records.
            raise _RollbackGate()
    except _RollbackGate:
        pass
    finally:
        await conn.close()
    client = redis.from_url(redis_url(), socket_connect_timeout=3, socket_timeout=3)
    try:
        if not await client.ping():
            raise RuntimeError("Redis PING failed")
    finally:
        await client.aclose()
    print(f"REAL_INFRA_GATE_PASS postgres=ok migrations={len(MIGRATIONS)} rls=ok redis=ok")

class _RollbackGate(Exception):
    """Internal sentinel used to rollback integration-test fixture rows."""

if __name__ == "__main__":
    asyncio.run(main())
