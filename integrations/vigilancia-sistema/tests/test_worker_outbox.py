"""Prueba la lógica del worker (validación + relay del outbox) sin RabbitMQ/Postgres: los módulos
de terceros se sustituyen por stubs SOLO si no están instalados."""
import asyncio, importlib.util, json, sys, types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _stub(name, **attrs):
    if name in sys.modules:
        return
    try:
        __import__(name)
    except ModuleNotFoundError:
        m = types.ModuleType(name)
        for k, v in attrs.items(): setattr(m, k, v)
        sys.modules[name] = m


class _Metric:
    def __init__(self, *a, **k): pass
    def labels(self, *a, **k): return self
    def inc(self, *a): pass
    def set(self, *a): pass

_stub("aio_pika", Message=lambda **kw: types.SimpleNamespace(**kw),
      DeliveryMode=types.SimpleNamespace(PERSISTENT=2), ExchangeType=types.SimpleNamespace(FANOUT="fanout"))
_stub("asyncpg")
_stub("prometheus_client", Counter=_Metric, Gauge=_Metric, CollectorRegistry=lambda: object(), start_http_server=lambda *a, **k: None)


def load_worker():
    src = str(ROOT / "services/worker-pool/src")
    if src not in sys.path: sys.path.insert(0, src)
    spec = importlib.util.spec_from_file_location("worker_main", ROOT / "services/worker-pool/src/main.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


GOOD = {"event_id": "e1", "device_id": "d1", "type": "MOTION", "priority": "SECURITY", "sequence_number": 1, "timestamp": 1}


def test_validate_event_rejects_untrusted_garbage():
    w = load_worker()
    assert w.validate_event(dict(GOOD)) == GOOD
    for bad in ([], "x", {k: v for k, v in GOOD.items() if k != "type"},
                {**GOOD, "device_id": ""}, {**GOOD, "device_id": "x" * 129},
                {**GOOD, "timestamp": -1}, {**GOOD, "sequence_number": -3}, {**GOOD, "sequence_number": "1"}):
        try:
            w.validate_event(bad); raise AssertionError(f"debió rechazar {bad!r}")
        except (ValueError, KeyError):
            pass


class _Tx:
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False

class FakeConn:
    def __init__(self, rows): self.rows, self.updates = rows, []
    def transaction(self): return _Tx()
    async def fetch(self, sql, *a): return list(self.rows)
    async def execute(self, sql, *a): self.updates.append((sql.split()[1], a))

class FakePool:
    def __init__(self, rows): self.conn = FakeConn(rows)
    def acquire(self): return self
    async def __aenter__(self): return self.conn
    async def __aexit__(self, *a): return False

class Ex:
    def __init__(self, fail_on=None): self.sent, self.fail_on = [], fail_on
    async def publish(self, msg, routing_key=""):
        if self.fail_on is not None and len(self.sent) + 1 == self.fail_on: raise ConnectionError("broker down")
        self.sent.append(msg.body)


def _row(i): return {"outbox_id": i, "routing_key": "", "payload": json.dumps({"n": i})}


def test_outbox_publishes_and_marks_rows():
    w = load_worker(); pool, ex = FakePool([_row(1), _row(2)]), Ex()
    assert asyncio.run(w.relay_outbox(pool, ex)) == 2 and len(ex.sent) == 2
    assert [u[1][0] for u in pool.conn.updates if u[0] == "event_outbox"] == [1, 2]


def test_outbox_failure_keeps_row_pending_with_backoff_and_stops():
    w = load_worker(); pool, ex = FakePool([_row(1), _row(2), _row(3)]), Ex(fail_on=2)
    assert asyncio.run(w.relay_outbox(pool, ex)) == 1          # 1 publicada, la 2ª falló, la 3ª no se intenta (orden)
    attempts = [u for u in pool.conn.updates if u[1] and u[1][0] == 2]
    assert len(attempts) == 1 and "broker down" in attempts[0][1][1]
    assert not any(u[1][0] == 3 for u in pool.conn.updates)
