from pathlib import Path


def test_maintenance_routes_are_registered_in_the_public_api():
    from backend.app.main import app

    paths = app.openapi()["paths"]
    expected_methods = {
        "/api/v1/maintenance/orders": {"get", "post"},
        "/api/v1/maintenance/orders/mine": {"get"},
        "/api/v1/maintenance/orders/{order_id}": {"get", "patch"},
        "/api/v1/maintenance/orders/{order_id}/approve": {"post"},
        "/api/v1/maintenance/orders/{order_id}/status": {"patch"},
        "/api/v1/maintenance/units": {"get"},
        "/api/v1/maintenance/residents": {"get", "post"},
        "/api/v1/maintenance/residents/{resident_id}": {"get", "put"},
        "/api/v1/maintenance/vendors": {"get", "post"},
        "/api/v1/maintenance/vendors/{vendor_id}": {"get", "put"},
        "/api/v1/tenants/current": {"get"},
    }

    for path, methods in expected_methods.items():
        assert methods <= paths[path].keys()


def test_maintenance_migration_enforces_tenant_isolation_and_append_only_events():
    migration = (
        Path(__file__).resolve().parents[2]
        / "migrations"
        / "sql"
        / "20261027_013_maintenance_operations.sql"
    )
    sql = migration.read_text(encoding="utf-8")

    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "app.current_tenant_id" in sql
    assert "maintenance_order_events_no_mutation" in sql
    assert "BEFORE UPDATE OR DELETE ON maintenance_order_events" in sql
    assert "UNIQUE (tenant_id, code)" in sql
