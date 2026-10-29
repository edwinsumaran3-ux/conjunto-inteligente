import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared/libs"))
import resilience


class Msg:
    def __init__(self, body=b"{}", redelivered=False):
        self.body, self.redelivered, self.message_id, self.headers = body, redelivered, "m1", {}
        self.calls = []
    async def ack(self): self.calls.append("ack")
    async def reject(self, requeue=False): self.calls.append(f"reject:{requeue}")
    async def nack(self, requeue=True): self.calls.append(f"nack:{requeue}")


class _Acq:
    def __init__(self, pool): self.pool = pool
    async def __aenter__(self):
        if self.pool.fail: raise ConnectionError("db down")
        return self.pool
    async def __aexit__(self, *a): return False


class Pool:
    def __init__(self, fail=False): self.fail, self.rows = fail, []
    def acquire(self): return _Acq(self)
    async def execute(self, sql, *args): self.rows.append(args)


def run(coro): return asyncio.run(coro)


def _go(msg, handler, pool):
    return run(resilience.process_message(msg, handler, pool=pool, service="s", queue="q", requeue_delay_s=0))


def test_success_acks():
    async def ok(m): pass
    m = Msg(); assert _go(m, ok, Pool()) == "acked" and m.calls == ["ack"]


def test_poison_json_goes_to_dead_letter_without_requeue():
    async def bad(m): json.loads(m.body)
    m, p = Msg(b"{not json"), Pool()
    assert _go(m, bad, p) == "dead-lettered"
    assert m.calls == ["reject:False"] and len(p.rows) == 1 and p.rows[0][6] == "JSONDecodeError"


def test_transient_error_requeues_once_then_dead_letters():
    async def flaky(m): raise ConnectionError("net")
    m1 = Msg(); assert _go(m1, flaky, Pool()) == "requeued" and m1.calls == ["nack:True"]
    m2, p = Msg(redelivered=True), Pool()
    assert _go(m2, flaky, p) == "dead-lettered" and m2.calls == ["reject:False"] and len(p.rows) == 1


def test_never_loses_message_when_dead_letter_store_is_down():
    async def bad(m): raise ValueError("x")
    m = Msg(); assert _go(m, bad, Pool(fail=True)) == "requeued" and m.calls == ["nack:True"]
    m = Msg(); assert _go(m, bad, None) == "requeued"


def test_sqlstate_classification():
    class E(Exception): sqlstate = "23505"
    class T(Exception): sqlstate = "40001"
    assert resilience.is_permanent_error(E()) and not resilience.is_permanent_error(T())
    assert not resilience.is_permanent_error(ConnectionError())


def test_service_copies_are_identical_to_canonical():
    root = Path(__file__).resolve().parents[1]
    canon = (root / "shared/libs/resilience.py").read_bytes()
    for svc in ("worker-pool", "correlation-engine", "incident-core", "agent-orchestrator"):
        assert (root / f"services/{svc}/src/resilience.py").read_bytes() == canon, svc
