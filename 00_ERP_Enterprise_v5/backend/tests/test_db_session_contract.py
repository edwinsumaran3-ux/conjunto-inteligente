import pytest

from backend.app.db import session as db_session


def test_database_url_is_required(monkeypatch):
    db_session._engine_and_factory.cache_clear()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PHASE13_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        db_session.get_session_factory()
    db_session._engine_and_factory.cache_clear()


def test_rejects_sync_or_unsupported_database_driver(monkeypatch):
    db_session._engine_and_factory.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    with pytest.raises(RuntimeError, match="Only postgresql\\+asyncpg"):
        db_session.get_session_factory()
    db_session._engine_and_factory.cache_clear()


def test_factory_uses_async_postgres_and_pool_health_options(monkeypatch):
    db_session._engine_and_factory.cache_clear()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:pass@localhost:5432/erp_test",
    )
    captured = {}

    class FakeEngine:
        url = type("URL", (), {"drivername": "postgresql+asyncpg"})()
        pool = type("Pool", (), {"_pre_ping": True})()

    def fake_create_async_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeEngine()

    monkeypatch.setattr(db_session, "create_async_engine", fake_create_async_engine)
    engine, factory = db_session._engine_and_factory()
    assert engine.url.drivername == "postgresql+asyncpg"
    assert factory.kw.get("expire_on_commit") is False
    assert captured["kwargs"]["pool_pre_ping"] is True
    assert captured["kwargs"]["pool_size"] == 5
    db_session._engine_and_factory.cache_clear()
