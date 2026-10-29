"""Alembic async (asyncpg). DATABASE_URL = postgresql+asyncpg://... Las revisiones aplican los .sql versionados en migrations/sql."""
import asyncio, os
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

config = context.config
URL = os.environ.get("DATABASE_URL") or os.environ.get("ALEMBIC_DATABASE_URL")

def _do(conn):
    context.configure(connection=conn, target_metadata=None, transactional_ddl=True)
    with context.begin_transaction(): context.run_migrations()

async def _online():
    if not URL: raise RuntimeError("DATABASE_URL no configurada")
    eng = create_async_engine(URL, poolclass=None) if False else create_async_engine(URL)
    async with eng.connect() as c:
        await c.run_sync(_do); await c.commit()
    await eng.dispose()

if context.is_offline_mode(): raise RuntimeError("modo offline no soportado: las revisiones ejecutan archivos SQL")
asyncio.run(_online())
