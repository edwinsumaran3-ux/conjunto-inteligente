"""Mantenimiento E2E sobre PostgreSQL real; requiere base desechable y confirmación explícita."""
from __future__ import annotations

import asyncio
import os
import pathlib
import uuid

import pytest
from sqlalchemy.engine import make_url

URL = os.getenv("PHASE13_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not URL,
    reason="requiere PostgreSQL real (PHASE13_DATABASE_URL)",
)
ROOT = pathlib.Path(__file__).resolve().parents[3]
MIGRATIONS = [
    ROOT / "backend/app/modules/digital_twin/migrations/001_outbox_events.sql",
    *sorted((ROOT / "migrations/sql").glob("2026*.sql")),
]
RAW = (URL or "").replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest.fixture(scope="module")
def maintenance_client():
    import asyncpg
    from fastapi.testclient import TestClient

    async def prepare_database():
        connection = await asyncpg.connect(RAW)
        try:
            await connection.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
            for migration in MIGRATIONS:
                await connection.execute(migration.read_text(encoding="utf-8"))
            await connection.execute(
                """DO $$BEGIN
                   IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='erp_app') THEN
                     CREATE ROLE erp_app LOGIN PASSWORD 'erp_app'
                       NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
                   END IF;
                   END$$;
                   ALTER ROLE erp_app PASSWORD 'erp_app';
                   GRANT ALL ON ALL TABLES IN SCHEMA public TO erp_app;
                   GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO erp_app;
                   GRANT USAGE ON SCHEMA public TO erp_app;
                   GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO erp_app;"""
            )
        finally:
            await connection.close()

    asyncio.run(prepare_database())

    tenant_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    resident_user_id = uuid.uuid4()
    property_node_id = uuid.uuid4()
    property_id = uuid.uuid4()
    assigned_unit_node_id = uuid.uuid4()
    assigned_unit_id = uuid.uuid4()
    other_unit_node_id = uuid.uuid4()
    other_unit_id = uuid.uuid4()

    async def seed_fixture_data():
        connection = await asyncpg.connect(RAW)
        try:
            async with connection.transaction():
                await connection.execute(
                    "INSERT INTO tenants(id,name) VALUES($1,$2)",
                    tenant_id,
                    "Maintenance E2E",
                )
                await connection.executemany(
                    """INSERT INTO users(id,tenant_id,email,password_hash)
                       VALUES($1,$2,$3,'not-used-by-token-tests')""",
                    [
                        (admin_id, tenant_id, "admin@maintenance.test"),
                        (resident_user_id, tenant_id, "resident@maintenance.test"),
                    ],
                )
                await connection.execute(
                    """INSERT INTO twin_nodes(id,tenant_id,node_type,code,name)
                       VALUES($1,$2,'building','E2E-BUILDING','Bloque E2E')""",
                    property_node_id,
                    tenant_id,
                )
                await connection.execute(
                    """INSERT INTO managed_properties
                       (id,tenant_id,root_node_id,property_type,code,name)
                       VALUES($1,$2,$3,'residential','E2E-PROPERTY','Propiedad E2E')""",
                    property_id,
                    tenant_id,
                    property_node_id,
                )
                for node_id, unit_id, code, name in (
                    (assigned_unit_node_id, assigned_unit_id, "E2E-UNIT-1", "Unidad asignada"),
                    (other_unit_node_id, other_unit_id, "E2E-UNIT-2", "Otra unidad"),
                ):
                    await connection.execute(
                        """INSERT INTO twin_nodes(id,tenant_id,node_type,code,name)
                           VALUES($1,$2,'unit',$3,$4)""",
                        node_id,
                        tenant_id,
                        f"NODE-{code}",
                        name,
                    )
                    await connection.execute(
                        """INSERT INTO managed_units
                           (id,tenant_id,property_id,node_id,unit_type,code,name)
                           VALUES($1,$2,$3,$4,'apartment',$5,$6)""",
                        unit_id,
                        tenant_id,
                        property_id,
                        node_id,
                        code,
                        name,
                    )
        finally:
            await connection.close()

    asyncio.run(seed_fixture_data())
    os.environ["DATABASE_URL"] = (
        make_url(RAW)
        .set(
            drivername="postgresql+asyncpg",
            username="erp_app",
            password="erp_app",
        )
        .render_as_string(hide_password=False)
    )
    os.environ["JWT_SECRET_KEY"] = "maintenance-e2e-jwt-secret-" + ("x" * 40)

    from backend.app.main import app
    from backend.app.core.security import create_access_token

    admin_headers = {
        "Authorization": "Bearer "
        + create_access_token(str(admin_id), str(tenant_id), ["admin"])
    }
    resident_headers = {
        "Authorization": "Bearer "
        + create_access_token(str(resident_user_id), str(tenant_id), ["resident"])
    }

    with TestClient(app) as client:
        yield {
            "client": client,
            "tenant_id": tenant_id,
            "resident_user_id": resident_user_id,
            "admin_headers": admin_headers,
            "resident_headers": resident_headers,
            "property_id": property_id,
            "assigned_unit_id": assigned_unit_id,
            "other_unit_id": other_unit_id,
        }


def test_maintenance_residents_orders_approval_history_and_rls(maintenance_client):
    from backend.app.core.security import create_access_token

    client = maintenance_client["client"]
    admin = maintenance_client["admin_headers"]
    resident = maintenance_client["resident_headers"]
    tenant_id = maintenance_client["tenant_id"]
    resident_user_id = maintenance_client["resident_user_id"]
    property_id = str(maintenance_client["property_id"])
    assigned_unit_id = str(maintenance_client["assigned_unit_id"])
    other_unit_id = str(maintenance_client["other_unit_id"])

    profile = client.post(
        "/api/v1/maintenance/residents",
        headers=admin,
        json={
            "user_id": str(resident_user_id),
            "full_name": "Residente E2E",
            "unit_ids": [assigned_unit_id],
            "primary_unit_id": assigned_unit_id,
        },
    )
    assert profile.status_code == 201, profile.text
    resident_id = profile.json()["id"]

    vendor_response = client.post(
        "/api/v1/maintenance/vendors",
        headers=admin,
        json={
            "name": "Proveedor E2E",
            "nit": f"900{uuid.uuid4().int % 10**9:09d}",
            "categories": ["iluminacion"],
            "status": "active",
        },
    )
    assert vendor_response.status_code == 201, vendor_response.text
    vendor_id = vendor_response.json()["id"]

    order_body = {
        "title": "Luminaria fuera de servicio",
        "description": "Solicitud E2E",
        "category": "iluminacion",
        "severity": "medium",
        "property_id": property_id,
        "unit_id": assigned_unit_id,
        "resident_id": str(uuid.uuid4()),
        "vendor_id": vendor_id,
    }
    forbidden_unit = client.post(
        "/api/v1/maintenance/orders",
        headers=resident,
        json={**order_body, "unit_id": other_unit_id},
    )
    assert forbidden_unit.status_code == 403
    assert forbidden_unit.json()["detail"]["code"] == "RESIDENT_UNIT_NOT_ASSIGNED"

    created = client.post(
        "/api/v1/maintenance/orders",
        headers=resident,
        json=order_body,
    )
    assert created.status_code == 201, created.text
    order_id = created.json()["id"]
    assert created.json()["status"] == "pending_approval"

    my_orders = client.get(
        "/api/v1/maintenance/orders/mine",
        headers=resident,
    )
    assert my_orders.status_code == 200, my_orders.text
    assert my_orders.json()["total"] == 1
    assert my_orders.json()["items"][0]["id"] == order_id

    other_tenant_headers = {
        "Authorization": "Bearer "
        + create_access_token(
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            ["admin"],
        )
    }
    hidden_from_other_tenant = client.get(
        f"/api/v1/maintenance/orders/{order_id}",
        headers=other_tenant_headers,
    )
    assert hidden_from_other_tenant.status_code == 404

    approved = client.post(
        f"/api/v1/maintenance/orders/{order_id}/approve",
        headers=admin,
        json={"note": "Aprobada por pruebas", "expected_version": 1},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "scheduled"
    assert approved.json()["version"] == 2

    transitioned = client.patch(
        f"/api/v1/maintenance/orders/{order_id}/status",
        headers=admin,
        json={"status": "in_progress", "expected_version": 2},
    )
    assert transitioned.status_code == 200, transitioned.text
    assert transitioned.json()["version"] == 3

    updated = client.patch(
        f"/api/v1/maintenance/orders/{order_id}",
        headers=admin,
        json={
            "description": "Diagnóstico en curso",
            "cost_cop": 125000,
            "expected_version": 3,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 4

    stale = client.patch(
        f"/api/v1/maintenance/orders/{order_id}/status",
        headers=admin,
        json={"status": "completed", "expected_version": 2},
    )
    assert stale.status_code == 409

    events = client.get(
        f"/api/v1/maintenance/orders/{order_id}/events",
        headers=admin,
    )
    assert events.status_code == 200, events.text
    assert [event["event_type"] for event in events.json()] == [
        "created",
        "approved",
        "status_changed",
        "details_updated",
    ]

    listed = client.get(
        "/api/v1/maintenance/orders",
        headers=admin,
        params={"status": "in_progress", "category": "iluminacion"},
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["resident_id"] == resident_id
    assert listed.json()["items"][0]["unit_id"] == assigned_unit_id
    assert listed.json()["items"][0]["vendor_id"] == vendor_id
    assert listed.json()["items"][0]["description"] == "Diagnóstico en curso"

    resident_orders = client.get(
        "/api/v1/maintenance/orders/mine",
        headers=resident,
        params={"status": "in_progress"},
    )
    assert resident_orders.status_code == 200, resident_orders.text
    assert resident_orders.json()["total"] == 1
    assert resident_orders.json()["items"][0]["status"] == "in_progress"

    current_tenant = client.get("/api/v1/tenants/current", headers=admin)
    assert current_tenant.status_code == 200
    assert current_tenant.json()["id"] == str(tenant_id)

    import asyncpg

    async def verify_history_is_append_only():
        connection = await asyncpg.connect(RAW)
        try:
            with pytest.raises(asyncpg.RaiseError, match="append-only"):
                await connection.execute(
                    """DELETE FROM maintenance_order_events
                       WHERE tenant_id=$1 AND order_id=$2""",
                    tenant_id,
                    uuid.UUID(order_id),
                )
        finally:
            await connection.close()

    asyncio.run(verify_history_is_append_only())
