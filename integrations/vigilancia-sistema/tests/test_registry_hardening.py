import asyncio, dataclasses, json, os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/agent-orchestrator/src"))
from equipment_contracts import (EquipmentCommand, EquipmentCommandOutcome, EquipmentTelemetry,
                                 EquipmentType, CommandAuthorizationResult)
from equipment_registry import EquipmentRegistry
from control.command_security import sign_for_equipment

KEYS = {"d1": "k1"}


class FakeJournal:
    def __init__(self, fail=False): self.rows, self.fail = {}, fail
    async def begin(self, c):
        if self.fail: raise ConnectionError("db")
        if c.command_id in self.rows: return "DUPLICATE_COMMAND"
        if any(r["nonce"] == c.nonce for r in self.rows.values()): return "REPLAYED_NONCE"
        self.rows[c.command_id] = {"nonce": c.nonce, "status": "RECEIVED", "reason": None}; return "OK"
    async def finish(self, cid, status, reason, response=None):
        r = self.rows[cid]
        if r["status"] == "RECEIVED": r.update(status=status, reason=reason)


class FakeAudit:
    def __init__(self): self.items = []
    async def record(self, **kw): self.items.append(kw["action"]); return True


class Adapter:
    equipment_id, equipment_type = "d1", EquipmentType.DRONE
    def __init__(self, auth=CommandAuthorizationResult.AUTHORIZED, boom=None, stop_boom=False):
        self.auth, self.boom, self.stop_boom, self.executed = auth, boom, stop_boom, 0
    is_connected = False
    def authorize(self, c):
        if self.boom == "authorize": raise RuntimeError("x")
        return self.auth
    async def execute(self, c):
        if self.boom == "execute": raise RuntimeError("x")
        self.executed += 1; return EquipmentCommandOutcome(True, "accepted")
    async def get_telemetry(self): return EquipmentTelemetry("d1", 0, "ok")
    async def emergency_stop(self):
        if self.stop_boom: raise RuntimeError("stuck")


def cmd(i=1, nonce=None, ttl=30, signed=True, issued_delta=0.0):
    now = time.time() + issued_delta
    c = EquipmentCommand(f"00000000-0000-0000-0000-{i:012d}", nonce or f"n{i}", EquipmentType.DRONE, "d1", "observe",
                         {}, now, now + ttl, "agent", "")
    return dataclasses.replace(c, signature=sign_for_equipment(c)) if signed else c


def run_with_keys(fn):
    os.environ["EQUIPMENT_HMAC_KEYS_JSON"] = json.dumps(KEYS)
    try: return asyncio.run(fn())
    finally: os.environ.pop("EQUIPMENT_HMAC_KEYS_JSON", None)


def make(adapter=None, journal=None):
    r = EquipmentRegistry(journal=journal if journal is not None else FakeJournal(), audit=FakeAudit())
    r.register(adapter or Adapter()); return r


def test_valid_signed_command_executes_and_closes_journal():
    async def go():
        r = make(); out = await r.dispatch(cmd())
        assert out.accepted and r._journal.rows[cmd().command_id]["status"] == "accepted" if False else out.accepted
        assert list(r._journal.rows.values())[0]["status"] == "accepted"
    run_with_keys(go)


def test_no_key_provisioned_means_unsigned_and_fail_closed():
    async def go():
        a = Adapter(); r = make(a)
        c = cmd(signed=False); c = dataclasses.replace(c, signature=sign_for_equipment(c))
        assert c.signature == ""
        out = await r.dispatch(c)
        assert not out.accepted and out.reason == "missing-verified-signature" and a.executed == 0
    os.environ.pop("EQUIPMENT_HMAC_KEYS_JSON", None); asyncio.run(go())


def test_forged_signature_rejected_and_journal_closed():
    async def go():
        a = Adapter(); r = make(a); c = dataclasses.replace(cmd(), signature="f" * 64)
        out = await r.dispatch(c)
        assert out.reason == "invalid-command-signature" and a.executed == 0
        assert list(r._journal.rows.values())[0]["status"] == "rejected"
    run_with_keys(go)


def test_early_rejections_no_longer_leave_journal_in_received():
    async def go():
        r = make(); c = dataclasses.replace(cmd(), equipment_id="ghost")
        out = await r.dispatch(c)
        assert out.reason == "unknown-equipment"
        assert list(r._journal.rows.values())[0]["status"] == "rejected"
        r2 = make(); out = await r2.dispatch(cmd(ttl=-5))
        assert out.reason == "invalid-command-window" and list(r2._journal.rows.values())[0]["status"] == "rejected"
    run_with_keys(go)


def test_duplicate_command_id_and_replayed_nonce_rejected_even_via_journal():
    async def go():
        a = Adapter(); r = make(a)
        assert (await r.dispatch(cmd(1, "same"))).accepted
        assert (await r.dispatch(cmd(1, "other"))).reason == "duplicate-command"   # mismo command_id
        r.__init__(journal=r._journal, audit=r._audit); r.register(a)           # "reinicio": se pierde la memoria
        assert (await r.dispatch(cmd(2, "same"))).reason == "replayed-nonce"      # la BD recuerda el nonce
        assert a.executed == 1
    run_with_keys(go)


def test_journal_down_is_fail_closed():
    async def go():
        a = Adapter(); r = make(a, FakeJournal(fail=True))
        out = await r.dispatch(cmd())
        assert not out.accepted and out.reason == "journal-unavailable" and a.executed == 0
    run_with_keys(go)


def test_excessive_ttl_and_future_issue_rejected():
    async def go():
        a = Adapter(); r = make(a)
        assert (await r.dispatch(cmd(1, ttl=3600))).reason == "invalid-command-window"
        assert (await r.dispatch(cmd(2, issued_delta=600))).reason == "invalid-command-window" and a.executed == 0
    run_with_keys(go)


def test_adapter_exceptions_are_contained():
    async def go():
        for boom, reason in (("authorize", "authorize-error"), ("execute", "adapter-exception:RuntimeError")):
            r = make(Adapter(boom=boom)); out = await r.dispatch(cmd())
            assert not out.accepted and out.reason == reason
    run_with_keys(go)


def test_non_authorized_adapter_blocks_execute():
    async def go():
        a = Adapter(auth=CommandAuthorizationResult.UNKNOWN_ISSUER); r = make(a)
        out = await r.dispatch(cmd()); assert out.reason == "UNKNOWN_ISSUER" and a.executed == 0
    run_with_keys(go)


def test_emergency_stop_reports_partial_failure_and_continues():
    async def go():
        r = EquipmentRegistry(journal=None, audit=FakeAudit())
        bad = Adapter(stop_boom=True)
        good = Adapter(); good.equipment_id = "d2"
        r.register(bad); r.register(good)
        res = await r.emergency_stop_all()
        assert res == {"d1": "error:RuntimeError", "d2": "ok"}
    asyncio.run(go())
