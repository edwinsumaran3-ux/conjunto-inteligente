import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "edge-gateway/src"))
from durable_buffer import DurableBuffer


def ev(i, prio="TELEMETRY"): return {"event_id": str(i), "priority": prio}


def test_persists_and_counts_across_restart():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "b.jsonl"); b = DurableBuffer(p)
        for i in range(3): b.append(ev(i))
        assert len(b) == 3 and len(DurableBuffer(p)) == 3


def test_flush_does_not_lose_events_appended_during_forwarding():
    with tempfile.TemporaryDirectory() as d:
        b = DurableBuffer(os.path.join(d, "b.jsonl"))
        for i in range(3): b.append(ev(i))
        snap = b.snapshot()
        b.append(ev("llegó-durante-el-reenvío"))      # el bug original perdía este evento
        b.commit_flush(snap, remaining=[snap[1]])
        ids = [json.loads(x)["event_id"] for x in b.snapshot()]
        assert ids == ["1", "llegó-durante-el-reenvío"] and len(b) == 2


def test_eviction_drops_lowest_priority_oldest_first():
    with tempfile.TemporaryDirectory() as d:
        b = DurableBuffer(os.path.join(d, "b.jsonl"), max_events=3)
        b.append(ev("c", "CRITICAL")); b.append(ev("t1")); b.append(ev("t2"))
        b.append(ev("new", "SECURITY"))
        ids = [json.loads(x)["event_id"] for x in b.snapshot()]
        assert "c" in ids and "t1" not in ids and "new" in ids and b.dropped == 1 and len(b) == 3


def test_critical_only_buffer_still_bounded():
    with tempfile.TemporaryDirectory() as d:
        b = DurableBuffer(os.path.join(d, "b.jsonl"), max_events=2)
        for i in range(4): b.append(ev(i, "CRITICAL"))
        assert len(b) == 2 and b.dropped == 2


def test_corrupt_and_rejected_lines_are_set_aside():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "b.jsonl"); b = DurableBuffer(p); b.append(ev(1))
        snap = b.snapshot() + ["{corrupta"]
        b.commit_flush(b.snapshot(), remaining=[], rejected=[snap[0]], corrupt=["{corrupta"])
        assert len(b) == 0
        assert Path(p + ".rejected").read_text().strip() and Path(p + ".corrupt").read_text().strip() == "{corrupta"


def test_resent_event_id_is_not_duplicated():
    with tempfile.TemporaryDirectory() as d:
        b = DurableBuffer(os.path.join(d, "b.jsonl"))
        assert b.append(ev("x")) is True
        assert b.append(ev("x")) is False and len(b) == 1       # el ESP32 reintenta el mismo event_id
        assert len(DurableBuffer(os.path.join(d, "b.jsonl"))) == 1
