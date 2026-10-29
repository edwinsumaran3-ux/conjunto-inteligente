"""Humo de TODOS los endpoints contra PostgreSQL real: ninguno debe terminar en excepción no controlada (500).
Cada operación se invoca con un cuerpo mínimo derivado de su esquema OpenAPI; 2xx/3xx/4xx = el sistema respondió con control."""
import asyncio, os, pathlib, uuid, json
import pytest

URL = os.getenv("PHASE13_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="requiere PostgreSQL real")
ROOT = pathlib.Path(__file__).resolve().parents[3]
MIGS = [ROOT/"backend/app/modules/digital_twin/migrations/001_outbox_events.sql", *sorted((ROOT/"migrations/sql").glob("2026*.sql"))]
RAW = (URL or "").replace("postgresql+asyncpg://", "postgresql://", 1)
SKIP_PREFIX = ("/healthz", "/readyz", "/docs", "/redoc", "/openapi.json", "/metrics")

def dummy(schema, spec, depth=0):
    if "$ref" in schema: return dummy(spec["components"]["schemas"][schema["$ref"].split("/")[-1]], spec, depth)
    for k in ("anyOf", "oneOf"):
        if k in schema:
            opts = [o for o in schema[k] if o.get("type") != "null"]; return dummy(opts[0], spec, depth) if opts else None
    if "allOf" in schema: return dummy(schema["allOf"][0], spec, depth)
    if "enum" in schema: return schema["enum"][0]
    if "const" in schema: return schema["const"]
    t = schema.get("type")
    if t == "string":
        f = schema.get("format")
        if f == "uuid": return str(uuid.uuid4())
        if f == "date": return "2026-01-15"
        if f == "date-time": return "2026-01-15T10:00:00Z"
        if f == "email": return "a@b.co"
        n = max(schema.get("minLength", 1), 1); return ("x" * n)[:max(n, 1)] if not schema.get("pattern") else "x" * n
    if t == "integer": return max(int(schema.get("minimum", 1)), int(schema.get("exclusiveMinimum", 0)) + 1 if "exclusiveMinimum" in schema else 1)
    if t == "number": return float(schema.get("minimum", 1)) if "exclusiveMinimum" not in schema else float(schema["exclusiveMinimum"]) + 1
    if t == "boolean": return True
    if t == "array":
        if depth > 4: return []
        return [dummy(schema.get("items", {}), spec, depth + 1) for _ in range(max(schema.get("minItems", 0), 0))]
    if t == "object" or "properties" in schema:
        if depth > 4: return {}
        req = schema.get("required", []); props = schema.get("properties", {})
        return {k: dummy(v, spec, depth + 1) for k, v in props.items() if k in req}
    return None

@pytest.fixture(scope="module")
def client():
    import asyncpg
    from fastapi.testclient import TestClient
    async def prep():
        c = await asyncpg.connect(RAW); await c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        for m in MIGS: await c.execute(m.read_text())
        await c.execute("DO $$BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='erp_app') THEN CREATE ROLE erp_app LOGIN PASSWORD 'erp_app' NOSUPERUSER NOBYPASSRLS; END IF; END$$;"
                        "GRANT ALL ON ALL TABLES IN SCHEMA public TO erp_app; GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO erp_app; GRANT USAGE ON SCHEMA public TO erp_app; GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO erp_app;")
        await c.close()
    asyncio.run(prep())
    os.environ["DATABASE_URL"] = RAW.replace("postgresql://", "postgresql+asyncpg://", 1).replace("//erp@", "//erp_app:erp_app@"); os.environ["JWT_SECRET_KEY"] = "x" * 48
    from backend.app.main import app
    with TestClient(app, raise_server_exceptions=True) as c: yield c

def test_ningun_endpoint_revienta(client):
    from backend.app.core.security import create_access_token
    from backend.app.main import app
    spec = app.openapi(); T = str(uuid.uuid4())
    H = {"Authorization": "Bearer " + create_access_token(str(uuid.uuid4()), T, ["admin"])}
    crashes, total = [], 0
    for path, ops in spec["paths"].items():
        if path.startswith(SKIP_PREFIX) or "/auth/" in path: continue
        for method, op in ops.items():
            if method not in ("get", "post", "put", "patch", "delete"): continue
            url = path; q = {}
            for p in op.get("parameters", []):
                v = dummy(p["schema"], spec)
                if p["in"] == "path": url = url.replace("{" + p["name"] + "}", str(v))
                elif p.get("required"): q[p["name"]] = v
            body = None; files = None
            rb = op.get("requestBody", {}).get("content", {})
            if "application/json" in rb: body = dummy(rb["application/json"]["schema"], spec)
            elif rb: continue  # multipart/octet: cubierto en pruebas específicas
            total += 1
            try: r = client.request(method.upper(), url, params=q, json=body, headers=H)
            except Exception as e: crashes.append((method.upper(), path, f"{type(e).__name__}: {str(e).splitlines()[0][:170]}")); continue
            if r.status_code >= 500 and r.status_code != 503: crashes.append((method.upper(), path, f"HTTP {r.status_code}"))
    report = "\n".join(f"  {m} {p} -> {e}" for m, p, e in crashes)
    assert not crashes, f"{len(crashes)}/{total} endpoints terminaron en error no controlado:\n{report}"
