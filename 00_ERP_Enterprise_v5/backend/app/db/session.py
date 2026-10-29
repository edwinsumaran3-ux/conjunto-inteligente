"""Async SQLAlchemy session lifecycle for the ERP backend.

The engine is created lazily so importing API modules does not require a live
database. Production deployments must provide DATABASE_URL (or the legacy
PHASE13_DATABASE_URL) as an async PostgreSQL URL. SQLite is intentionally not
silently selected as a fallback.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import AsyncIterator

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _database_url() -> str:
    raw = os.getenv("DATABASE_URL") or os.getenv("PHASE13_DATABASE_URL")
    if not raw:
        raise RuntimeError(
            "DATABASE_URL is required; set it to a PostgreSQL async URL "
            "such as postgresql+asyncpg://user:password@host:5432/database"
        )
    try:
        url = make_url(raw)
    except Exception as exc:
        raise RuntimeError("DATABASE_URL is not a valid SQLAlchemy URL") from exc
    if url.drivername not in {"postgresql+asyncpg"}:
        raise RuntimeError(
            "Only postgresql+asyncpg is supported by the ERP session layer; "
            f"received driver {url.drivername!r}"
        )
    return raw


@lru_cache(maxsize=1)
def _engine_and_factory() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    url = _database_url()
    engine = create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800")),
    )
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return engine, factory


def get_engine() -> AsyncEngine:
    """Engine compartido (inicialización perezosa)."""
    return _engine_and_factory()[0]


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the shared async session factory, initialized on first use."""
    return _engine_and_factory()[1]


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session with explicit commit/rollback."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Dispose pooled connections and reset the lazy singleton (for shutdown/tests)."""
    if _engine_and_factory.cache_info().currsize:
        engine, _ = _engine_and_factory()
        await engine.dispose()
    _engine_and_factory.cache_clear()
