"""Despliegue: aplicador de migraciones (todas, idempotente, inmutables), rol de aplicación sin privilegios y guarda de RLS al arrancar."""
import asyncio, os, pathlib, sys
import pytest
from sqlalchemy.engine import make_url

URL = os.getenv("PHASE13_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="requiere PostgreSQL real")
ROOT = pathlib.Path(__file__).resolve().parents[3]
RAW = (URL or "").replace("postgresql+asyncpg://", "postgresql://", 1)

def test_migraciones_rol_de_aplicacion_y_guarda_rls(monkeypatch):
    import asyncpg
    sys.path.insert(0, str(ROOT / "scripts"))
    import apply_sql_migrations as M
    monkeypatch.setenv("MIGRATION_DATABASE_URL", RAW); monkeypatch.setenv("APP_DB_PASSWORD", "una-clave-larga-1234567890")
    async def q(sql, *a):
        c = await asyncpg.connect(RAW)
        try: return await c.fetch(sql, *a)
        finally: await c.close()
    async def run():
        c = await asyncpg.connect(RAW); await c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"); await c.close()
        assert await M.main(check_only=True) == 1, "base vacía: hay migraciones pendientes"
        assert await M.main() == 0
        n = len(M.FILES); assert (await q("SELECT count(*) FROM schema_migrations"))[0][0] == n
        assert await M.main() == 0 and (await q("SELECT count(*) FROM schema_migrations"))[0][0] == n, "segunda ejecución: idempotente"
        assert await M.main(check_only=True) == 0
        roles = {r["rolname"]: (r["rolsuper"], r["rolbypassrls"]) for r in await q("SELECT rolname,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=ANY($1)", ["erp", "erp_app"])}
        assert roles["erp_app"] == (False, False), "el rol de la API no puede ser superusuario ni BYPASSRLS"
        # las migraciones son inmutables
        await q("UPDATE schema_migrations SET sha256='x' WHERE filename=(SELECT filename FROM schema_migrations ORDER BY filename LIMIT 1)")
        with pytest.raises(RuntimeError, match="MIGRACION MODIFICADA"): await M.main()
        # guarda de arranque
        from sqlalchemy.ext.asyncio import create_async_engine
        from backend.app.db.rls_guard import assert_rls_effective
        owner = create_async_engine(URL); app_url = make_url(URL).set(username="erp_app", password="una-clave-larga-1234567890").render_as_string(hide_password=False); app = create_async_engine(app_url)
        try:
            assert await assert_rls_effective(owner, production=False) is False
            with pytest.raises(RuntimeError, match="ARRANQUE RECHAZADO"): await assert_rls_effective(owner, production=True)
            assert await assert_rls_effective(app, production=True) is True
        finally: await owner.dispose(); await app.dispose()
    try: asyncio.run(run())
    finally:   # las demás pruebas E2E se conectan como erp_app/erp_app
        asyncio.run(q("ALTER ROLE erp_app PASSWORD 'erp_app'")) if True else None
