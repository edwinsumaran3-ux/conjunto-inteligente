import re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infrastructure/postgres"))
import migrate, schema_check

MIG_DIR = Path(__file__).resolve().parents[1] / "infrastructure/postgres/migrations"


def test_migrations_sequential_and_manifest_matches():
    ms = migrate.discover_migrations()
    assert [m.version for m in ms] == [f"{i:04d}" for i in range(1, len(ms) + 1)]
    assert migrate.verify_manifest(ms, migrate.read_manifest()) == []


def test_baseline_is_byte_identical_to_legacy_init_sql():
    legacy = (MIG_DIR.parent / "init.sql").read_text(encoding="utf-8")
    assert (MIG_DIR / "0001_baseline.sql").read_text(encoding="utf-8") == legacy  # init.sql no se tocó ni se borró


def test_tampered_migration_is_detected():
    ms = migrate.discover_migrations()
    applied = {m.version: m.checksum for m in ms}
    applied["0003"] = "0" * 64
    pending, problems = migrate.plan(ms, applied)
    assert pending == [] and any("ALTERADA" in p for p in problems)


def test_pending_and_orphan_detection():
    ms = migrate.discover_migrations()
    applied = {m.version: m.checksum for m in ms[:3]}
    pending, problems = migrate.plan(ms, applied)
    assert [m.version for m in pending] == [m.version for m in ms[3:]] and problems == []
    applied["0099"] = "x"
    _, problems = migrate.plan(ms, applied)
    assert any("0099" in p for p in problems)


def test_out_of_order_pending_is_flagged():
    ms = migrate.discover_migrations()
    applied = {ms[0].version: ms[0].checksum, ms[2].version: ms[2].checksum}  # falta 0002
    _, problems = migrate.plan(ms, applied)
    assert any("posteriores" in p for p in problems)


def test_static_schema_check_passes():
    schema = schema_check.analyze()
    problems = schema.problems + schema_check.python_sql_problems(schema)
    assert problems == [], problems


def test_expected_core_tables_exist():
    t = schema_check.analyze().tables
    for name in ("events", "incidents", "devices", "agent_actions", "agent_approvals", "equipment",
                 "equipment_command_journal", "audit_log", "event_outbox", "dead_letter_messages",
                 "tenants", "sites", "zones", "operators", "incident_timeline", "ai_provider_policies",
                 "neural_inference_audit", "notifications", "incident_events"):
        assert name in t and t[name].has_pk, name


def test_checker_catches_bad_sql():
    s = schema_check.Schema()
    s.feed("x.sql", "CREATE TABLE a (id int);")  # sin PK
    s.feed("x.sql", "CREATE TABLE b (id int PRIMARY KEY, a_id int REFERENCES zzz(id));")
    s.feed("x.sql", "DROP TABLE a;")
    s.feed("x.sql", "CREATE INDEX ix ON b(nope);")
    msgs = " | ".join(s.problems)
    assert "sin PRIMARY KEY" in msgs and "tabla inexistente zzz" in msgs
    assert "destructiva" in msgs and "columna inexistente b.nope" in msgs


def test_no_destructive_statements_in_new_migrations():
    for p in sorted(MIG_DIR.glob("000[2-8]_*.sql")):
        for stmt in schema_check.strip_sql(p.read_text(encoding="utf-8")):
            masked = schema_check._mask_literals(stmt)
            if schema_check.DESTRUCTIVE.search(masked):
                assert any(re.fullmatch(a, " ".join(stmt.split()), re.I) for a in schema_check.ALLOWED_DESTRUCTIVE), stmt
