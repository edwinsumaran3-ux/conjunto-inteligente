"""Aplica TODAS las migraciones SQL en orden con un registro (schema_migrations: archivo + sha256) y aprovisiona el rol de aplicación.
- Idempotente: lo ya aplicado se omite; si un archivo aplicado CAMBIÓ de contenido, aborta (las migraciones son inmutables).
- Se ejecuta con el rol PROPIETARIO (MIGRATION_DATABASE_URL). La API corre con el rol `erp_app` (NOSUPERUSER, NOBYPASSRLS): con un superusuario
  PostgreSQL ignora RLS y un tenant vería los datos de otro. El password de erp_app viene de APP_DB_PASSWORD.
Uso: python scripts/apply_sql_migrations.py [--check]   (--check: falla si hay migraciones pendientes, sin aplicar nada)."""
from __future__ import annotations
import asyncio, hashlib, os, sys
from pathlib import Path
import asyncpg

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / "backend/app/modules/digital_twin/migrations/001_outbox_events.sql", *sorted((ROOT / "migrations/sql").glob("2026*.sql"))]
APP_ROLE = os.getenv("APP_DB_ROLE", "erp_app")

def _dsn() -> str:
    raw = os.getenv("MIGRATION_DATABASE_URL") or os.getenv("PHASE13_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not raw: raise RuntimeError("MIGRATION_DATABASE_URL (rol propietario) es obligatoria")
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)

async def provision_app_role(conn: asyncpg.Connection) -> None:
    pwd = os.getenv("APP_DB_PASSWORD")
    if not pwd or len(pwd) < 16: raise RuntimeError("APP_DB_PASSWORD (16+ caracteres) es obligatoria para crear el rol de aplicación")
    if not APP_ROLE.replace("_", "").isalnum(): raise RuntimeError("APP_DB_ROLE inválido")
    role = await conn.fetchrow("SELECT rolsuper, rolbypassrls, rolcanlogin FROM pg_roles WHERE rolname=$1", APP_ROLE)
    if role is None:
        await conn.execute(f"CREATE ROLE {APP_ROLE} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE")
        role = await conn.fetchrow("SELECT rolsuper, rolbypassrls, rolcanlogin FROM pg_roles WHERE rolname=$1", APP_ROLE)
    if role["rolsuper"] or role["rolbypassrls"] or not role["rolcanlogin"]:
        raise RuntimeError(f"El rol {APP_ROLE} debe ser LOGIN, NOSUPERUSER y NOBYPASSRLS")
    await conn.execute(await conn.fetchval("SELECT format('ALTER ROLE %I PASSWORD %L', $1::text, $2::text)", APP_ROLE, pwd))
    db = await conn.fetchval("SELECT current_database()")
    await conn.execute(f'GRANT CONNECT ON DATABASE "{db}" TO {APP_ROLE}; GRANT USAGE ON SCHEMA public TO {APP_ROLE};'
                       f"GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}; GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE};"
                       f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO {APP_ROLE};"
                       f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO {APP_ROLE};"
                       f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE,SELECT ON SEQUENCES TO {APP_ROLE}; ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO {APP_ROLE};"
                       f"REVOKE ALL ON schema_migrations FROM {APP_ROLE};")

async def main(check_only: bool = False) -> int:
    conn = await asyncpg.connect(_dsn())
    try:
        await conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations(filename text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())")
        done = {r["filename"]: r["sha256"] for r in await conn.fetch("SELECT filename,sha256 FROM schema_migrations")}
        pending = []
        for f in FILES:
            if not f.is_file(): raise FileNotFoundError(f)
            name, sha = str(f.relative_to(ROOT)), hashlib.sha256(f.read_bytes()).hexdigest()
            if name in done:
                if done[name] != sha: raise RuntimeError(f"MIGRACION MODIFICADA tras aplicarse: {name} (las migraciones son inmutables; crea una nueva)")
                continue
            pending.append((f, name, sha))
        if check_only:
            print(f"PENDING {len(pending)}"); return 1 if pending else 0
        for f, name, sha in pending:
            async with conn.transaction():
                await conn.execute(f.read_text(encoding="utf-8")); await conn.execute("INSERT INTO schema_migrations(filename,sha256) VALUES($1,$2)", name, sha)
            print(f"APPLIED {name}")
        await provision_app_role(conn)
        print(f"SQL_MIGRATIONS_APPLIED new={len(pending)} total={len(FILES)} app_role={APP_ROLE}")
        return 0
    finally: await conn.close()

if __name__ == "__main__": sys.exit(asyncio.run(main("--check" in sys.argv)))
