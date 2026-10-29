from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import AuthContext, get_auth_context, get_tenant_session

router = APIRouter(prefix="/maintenance", tags=["maintenance"])

MANAGER_ROLES = {
    "admin",
    "administrator",
    "maintenance_manager",
    "property_manager",
}
ADMIN_ROLES = {"admin", "administrator", "security_admin"}
ORDER_STATUSES = {
    "pending_approval",
    "critical",
    "scheduled",
    "in_progress",
    "pending_quote",
    "blocked",
    "completed",
    "cancelled",
}
ORDER_CATEGORIES = {
    "iluminacion",
    "electrico",
    "hidrosanitario",
    "areas_verdes",
    "parqueaderos",
    "seguridad",
    "edificacion",
    "ascensores",
    "piscina",
    "contra_incendio",
    "telecomunicaciones",
    "unknown",
}
VENDOR_STATUSES = {"active", "suspended", "inactive"}
ORDER_TRANSITIONS = {
    "scheduled": {"in_progress", "pending_quote", "blocked", "cancelled"},
    "in_progress": {"pending_quote", "blocked", "completed", "cancelled"},
    "pending_quote": {"scheduled", "cancelled"},
    "blocked": {"scheduled", "in_progress", "cancelled"},
}


class ResidentIn(BaseModel):
    user_id: UUID
    full_name: str = Field(min_length=1, max_length=240)
    phone: str | None = Field(default=None, max_length=40)
    unit_ids: list[UUID] = Field(min_length=1, max_length=20)
    primary_unit_id: UUID


class ResidentUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=240)
    phone: str | None = Field(default=None, max_length=40)
    active: bool
    unit_ids: list[UUID] = Field(min_length=1, max_length=20)
    primary_unit_id: UUID


class VendorIn(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    nit: str = Field(min_length=3, max_length=32)
    categories: list[str] = Field(default_factory=list, max_length=20)
    status: str = "active"
    documents_valid_until: date | None = None
    rating: Decimal | None = Field(default=None, ge=0, le=5, max_digits=3, decimal_places=2)


class VendorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    nit: str | None = Field(default=None, min_length=3, max_length=32)
    categories: list[str] | None = Field(default=None, max_length=20)
    status: str | None = None
    documents_valid_until: date | None = None
    rating: Decimal | None = Field(default=None, ge=0, le=5, max_digits=3, decimal_places=2)


class OrderIn(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default="", max_length=12000)
    category: str = Field(min_length=1, max_length=48)
    severity: str = Field(default="medium", pattern="^(info|low|medium|high|critical)$")
    property_id: UUID | None = None
    unit_id: UUID | None = None
    asset_node_id: UUID | None = None
    resident_id: UUID | None = None
    vendor_id: UUID | None = None
    cost_cop: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    sla_due_at: datetime | None = None


class OrderStatusIn(BaseModel):
    status: str
    note: str | None = Field(default=None, max_length=500)
    expected_version: int = Field(ge=1)


class ApprovalIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)
    expected_version: int = Field(ge=1)


class OrderUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=12000)
    vendor_id: UUID | None = None
    cost_cop: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    sla_due_at: datetime | None = None
    expected_version: int = Field(ge=1)


def _tenant(auth: AuthContext) -> UUID:
    return UUID(auth.tenant_id)


def _actor(auth: AuthContext) -> UUID:
    return UUID(auth.user_id)


def _require_manager(auth: AuthContext) -> None:
    if not MANAGER_ROLES.intersection(auth.roles):
        raise HTTPException(403, detail={"code": "MAINTENANCE_MANAGER_ROLE_REQUIRED"})


def _require_admin(auth: AuthContext) -> None:
    if not ADMIN_ROLES.intersection(auth.roles):
        raise HTTPException(403, detail={"code": "MAINTENANCE_ADMIN_ROLE_REQUIRED"})


def _category(value: str) -> str:
    if value not in ORDER_CATEGORIES:
        raise HTTPException(422, detail={"code": "MAINTENANCE_CATEGORY_UNSUPPORTED"})
    return value


async def _write_audit(
    session: AsyncSession,
    tenant_id: UUID,
    actor_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID,
    details: dict[str, Any],
) -> None:
    await session.execute(
        text(
            """INSERT INTO audit_log
               (id,tenant_id,actor_id,action,entity_type,entity_id,after_state)
               VALUES(:id,:tenant,:actor,:action,:entity_type,:entity_id,CAST(:details AS jsonb))"""
        ),
        {
            "id": uuid4(),
            "tenant": tenant_id,
            "actor": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "details": json.dumps(details, default=str, sort_keys=True),
        },
    )


async def _record_order_event(
    session: AsyncSession,
    tenant_id: UUID,
    order_id: UUID,
    actor_id: UUID,
    event_type: str,
    from_status: str | None,
    to_status: str | None,
    details: dict[str, Any] | None = None,
) -> None:
    await session.execute(
        text(
            """INSERT INTO maintenance_order_events
               (tenant_id,order_id,actor_id,event_type,from_status,to_status,details)
               VALUES(:tenant,:order,:actor,:type,:from_status,:to_status,CAST(:details AS jsonb))"""
        ),
        {
            "tenant": tenant_id,
            "order": order_id,
            "actor": actor_id,
            "type": event_type,
            "from_status": from_status,
            "to_status": to_status,
            "details": json.dumps(details or {}, default=str, sort_keys=True),
        },
    )


async def _validate_units(
    session: AsyncSession, tenant_id: UUID, unit_ids: list[UUID]
) -> None:
    if len(set(unit_ids)) != len(unit_ids):
        raise HTTPException(422, detail={"code": "DUPLICATE_RESIDENT_UNIT"})
    found = (
        await session.execute(
            text(
                "SELECT id FROM managed_units WHERE tenant_id=:tenant AND id=ANY(:ids)"
            ),
            {"tenant": tenant_id, "ids": unit_ids},
        )
    ).scalars().all()
    if len(found) != len(unit_ids):
        raise HTTPException(422, detail={"code": "RESIDENT_UNIT_NOT_FOUND"})


def _resident_query() -> str:
    return """
        SELECT r.id,r.user_id,r.full_name,u.email,r.phone,r.active,
               primary_unit.id AS primary_unit_id,
               primary_unit.code AS unit_code,primary_unit.name AS unit_name,
               primary_property.name AS property_name,
               COALESCE(units.unit_ids,'[]'::jsonb) AS unit_ids
        FROM maintenance_residents r
        JOIN users u ON u.tenant_id=r.tenant_id AND u.id=r.user_id
        LEFT JOIN LATERAL (
          SELECT mu.id,mu.code,mu.name,mu.property_id
          FROM maintenance_resident_units ru
          JOIN managed_units mu ON mu.tenant_id=ru.tenant_id AND mu.id=ru.unit_id
          WHERE ru.tenant_id=r.tenant_id AND ru.resident_id=r.id
            AND ru.is_primary AND ru.valid_from<=CURRENT_DATE
            AND (ru.valid_until IS NULL OR ru.valid_until>=CURRENT_DATE)
          ORDER BY ru.valid_from DESC LIMIT 1
        ) primary_unit ON true
        LEFT JOIN managed_properties primary_property
          ON primary_property.tenant_id=r.tenant_id
         AND primary_property.id=primary_unit.property_id
        LEFT JOIN LATERAL (
          SELECT jsonb_agg(mu.id ORDER BY mu.code) AS unit_ids
          FROM maintenance_resident_units ru
          JOIN managed_units mu ON mu.tenant_id=ru.tenant_id AND mu.id=ru.unit_id
          WHERE ru.tenant_id=r.tenant_id AND ru.resident_id=r.id
            AND ru.valid_from<=CURRENT_DATE
            AND (ru.valid_until IS NULL OR ru.valid_until>=CURRENT_DATE)
        ) units ON true
        WHERE r.tenant_id=:tenant
    """


@router.get("/units")
async def list_maintenance_units(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    q: str | None = Query(default=None, max_length=160),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    _require_manager(auth)
    tenant_id = _tenant(auth)
    query = """
        SELECT mu.id,mu.property_id,mu.code,mu.name,mu.unit_type,
               mp.name AS property_name,mu.occupancy_status
        FROM managed_units mu
        JOIN managed_properties mp
          ON mp.tenant_id=mu.tenant_id AND mp.id=mu.property_id
        WHERE mu.tenant_id=:tenant
    """
    params: dict[str, Any] = {"tenant": tenant_id}
    if q:
        query += " AND (mu.code ILIKE :q OR mu.name ILIKE :q OR mp.name ILIKE :q)"
        params["q"] = f"%{q}%"
    total = int(
        await session.scalar(
            text(f"SELECT count(*) FROM ({query}) units"),
            params,
        )
        or 0
    )
    params.update({"limit": page_size, "offset": (page - 1) * page_size})
    rows = (
        await session.execute(
            text(query + " ORDER BY mp.name,mu.code,mu.id LIMIT :limit OFFSET :offset"),
            params,
        )
    ).mappings().all()
    return {
        "items": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/residents")
async def list_residents(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    tower: str | None = Query(default=None, max_length=160),
    q: str | None = Query(default=None, max_length=160),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    _require_manager(auth)
    tenant_id = _tenant(auth)
    query = _resident_query()
    params: dict[str, Any] = {"tenant": tenant_id}
    if tower:
        query += " AND primary_property.name ILIKE :tower"
        params["tower"] = f"%{tower}%"
    if q:
        query += " AND (r.full_name ILIKE :q OR u.email ILIKE :q OR primary_unit.code ILIKE :q)"
        params["q"] = f"%{q}%"
    count_sql = f"SELECT count(*) FROM ({query}) residents"
    total = int(await session.scalar(text(count_sql), params) or 0)
    params.update({"limit": page_size, "offset": (page - 1) * page_size})
    rows = (
        await session.execute(
            text(query + " ORDER BY r.full_name,r.id LIMIT :limit OFFSET :offset"),
            params,
        )
    ).mappings().all()
    return {
        "items": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/residents/{resident_id}")
async def get_resident(
    resident_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    _require_manager(auth)
    row = (
        await session.execute(
            text(_resident_query() + " AND r.id=:resident_id"),
            {"tenant": _tenant(auth), "resident_id": resident_id},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(404, detail={"code": "RESIDENT_NOT_FOUND"})
    return dict(row)


@router.post("/residents", status_code=201)
async def create_resident(
    body: ResidentIn,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    _require_admin(auth)
    tenant_id = _tenant(auth)
    if body.primary_unit_id not in body.unit_ids:
        raise HTTPException(422, detail={"code": "PRIMARY_UNIT_MUST_BE_ASSIGNED"})
    await _validate_units(session, tenant_id, body.unit_ids)
    user = (
        await session.execute(
            text("SELECT id FROM users WHERE tenant_id=:tenant AND id=:user AND is_active"),
            {"tenant": tenant_id, "user": body.user_id},
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(422, detail={"code": "RESIDENT_USER_NOT_FOUND_OR_INACTIVE"})

    resident_id = uuid4()
    try:
        await session.execute(
            text(
                """INSERT INTO maintenance_residents
                   (id,tenant_id,user_id,full_name,phone)
                   VALUES(:id,:tenant,:user,:name,:phone)"""
            ),
            {
                "id": resident_id,
                "tenant": tenant_id,
                "user": body.user_id,
                "name": body.full_name.strip(),
                "phone": body.phone,
            },
        )
        await session.execute(
            text(
                """INSERT INTO maintenance_resident_units
                   (tenant_id,resident_id,unit_id,is_primary)
                   VALUES(:tenant,:resident,:unit,:primary)
                   ON CONFLICT(tenant_id,resident_id,unit_id,valid_from)
                   DO UPDATE SET valid_until=NULL,is_primary=EXCLUDED.is_primary"""
            ),
            [
                {
                    "tenant": tenant_id,
                    "resident": resident_id,
                    "unit": unit_id,
                    "primary": unit_id == body.primary_unit_id,
                }
                for unit_id in body.unit_ids
            ],
        )
    except IntegrityError as exc:
        raise HTTPException(409, detail={"code": "RESIDENT_PROFILE_ALREADY_EXISTS"}) from exc

    await _write_audit(
        session,
        tenant_id,
        _actor(auth),
        "maintenance.resident.created",
        "MaintenanceResident",
        resident_id,
        {"user_id": body.user_id, "unit_ids": body.unit_ids},
    )
    return {"id": str(resident_id), "status": "created"}


@router.put("/residents/{resident_id}")
async def update_resident(
    resident_id: UUID,
    body: ResidentUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    _require_admin(auth)
    tenant_id = _tenant(auth)
    if body.primary_unit_id not in body.unit_ids:
        raise HTTPException(422, detail={"code": "PRIMARY_UNIT_MUST_BE_ASSIGNED"})
    await _validate_units(session, tenant_id, body.unit_ids)
    current = (
        await session.execute(
            text(
                "SELECT id FROM maintenance_residents "
                "WHERE tenant_id=:tenant AND id=:resident FOR UPDATE"
            ),
            {"tenant": tenant_id, "resident": resident_id},
        )
    ).scalar_one_or_none()
    if current is None:
        raise HTTPException(404, detail={"code": "RESIDENT_NOT_FOUND"})

    await session.execute(
        text(
            """UPDATE maintenance_residents
               SET full_name=:name,phone=:phone,active=:active,updated_at=now()
               WHERE tenant_id=:tenant AND id=:resident"""
        ),
        {
            "tenant": tenant_id,
            "resident": resident_id,
            "name": body.full_name.strip(),
            "phone": body.phone,
            "active": body.active,
        },
    )
    await session.execute(
        text(
            """UPDATE maintenance_resident_units SET valid_until=CURRENT_DATE
               WHERE tenant_id=:tenant AND resident_id=:resident
                 AND valid_until IS NULL AND unit_id<>ALL(:unit_ids)"""
        ),
        {"tenant": tenant_id, "resident": resident_id, "unit_ids": body.unit_ids},
    )
    existing = (
        await session.execute(
            text(
                """SELECT unit_id FROM maintenance_resident_units
                   WHERE tenant_id=:tenant AND resident_id=:resident
                     AND valid_until IS NULL AND unit_id=ANY(:unit_ids)"""
            ),
            {"tenant": tenant_id, "resident": resident_id, "unit_ids": body.unit_ids},
        )
    ).scalars().all()
    existing_ids = set(existing)
    for unit_id in body.unit_ids:
        if unit_id not in existing_ids:
            await session.execute(
                text(
                    """INSERT INTO maintenance_resident_units
                       (tenant_id,resident_id,unit_id,is_primary)
                       VALUES(:tenant,:resident,:unit,:primary)"""
                ),
                {
                    "tenant": tenant_id,
                    "resident": resident_id,
                    "unit": unit_id,
                    "primary": unit_id == body.primary_unit_id,
                },
            )
    await session.execute(
        text(
            """UPDATE maintenance_resident_units SET is_primary=(unit_id=:primary)
               WHERE tenant_id=:tenant AND resident_id=:resident
                 AND valid_until IS NULL"""
        ),
        {"tenant": tenant_id, "resident": resident_id, "primary": body.primary_unit_id},
    )
    await _write_audit(
        session,
        tenant_id,
        _actor(auth),
        "maintenance.resident.updated",
        "MaintenanceResident",
        resident_id,
        {"active": body.active, "unit_ids": body.unit_ids},
    )
    return {"id": str(resident_id), "status": "updated"}


def _vendor_query() -> str:
    return """
        SELECT id,name,nit,categories,status,
               (documents_valid_until IS NOT NULL AND documents_valid_until>=CURRENT_DATE)
                 AS documents_current,
               documents_valid_until,rating,created_at,updated_at,version
        FROM maintenance_vendors WHERE tenant_id=:tenant
    """


@router.get("/vendors")
async def list_vendors(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    category: str | None = Query(default=None, max_length=48),
    status: str | None = Query(default=None, max_length=24),
    q: str | None = Query(default=None, max_length=160),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    _require_manager(auth)
    query = _vendor_query()
    params: dict[str, Any] = {"tenant": _tenant(auth)}
    if category:
        query += " AND :category=ANY(categories)"
        params["category"] = category
    if status:
        if status not in VENDOR_STATUSES:
            raise HTTPException(422, detail={"code": "VENDOR_STATUS_UNSUPPORTED"})
        query += " AND status=:status"
        params["status"] = status
    if q:
        query += " AND (name ILIKE :q OR nit ILIKE :q)"
        params["q"] = f"%{q}%"
    total = int(
        await session.scalar(
            text("SELECT count(*) FROM maintenance_vendors WHERE tenant_id=:tenant"
                 + query.split("WHERE tenant_id=:tenant", 1)[1]),
            params,
        )
        or 0
    )
    params.update({"limit": page_size, "offset": (page - 1) * page_size})
    rows = (
        await session.execute(
            text(query + " ORDER BY name,id LIMIT :limit OFFSET :offset"),
            params,
        )
    ).mappings().all()
    return {
        "items": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/vendors/{vendor_id}")
async def get_vendor(
    vendor_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    _require_manager(auth)
    row = (
        await session.execute(
            text(_vendor_query() + " AND id=:vendor"),
            {"tenant": _tenant(auth), "vendor": vendor_id},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(404, detail={"code": "VENDOR_NOT_FOUND"})
    return dict(row)


@router.post("/vendors", status_code=201)
async def create_vendor(
    body: VendorIn,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    _require_admin(auth)
    if body.status not in VENDOR_STATUSES:
        raise HTTPException(422, detail={"code": "VENDOR_STATUS_UNSUPPORTED"})
    if any(_category(category) != category for category in body.categories):
        raise HTTPException(422, detail={"code": "VENDOR_CATEGORY_UNSUPPORTED"})
    vendor_id = uuid4()
    tenant_id = _tenant(auth)
    try:
        await session.execute(
            text(
                """INSERT INTO maintenance_vendors
                   (id,tenant_id,name,nit,categories,status,documents_valid_until,
                    rating,created_by,updated_by)
                   VALUES(:id,:tenant,:name,:nit,:categories,:status,:documents_until,
                          :rating,:actor,:actor)"""
            ),
            {
                "id": vendor_id,
                "tenant": tenant_id,
                "name": body.name.strip(),
                "nit": body.nit.strip(),
                "categories": sorted(set(body.categories)),
                "status": body.status,
                "documents_until": body.documents_valid_until,
                "rating": body.rating,
                "actor": _actor(auth),
            },
        )
    except IntegrityError as exc:
        raise HTTPException(409, detail={"code": "VENDOR_NIT_ALREADY_EXISTS"}) from exc
    await _write_audit(
        session,
        tenant_id,
        _actor(auth),
        "maintenance.vendor.created",
        "MaintenanceVendor",
        vendor_id,
        {"nit": body.nit, "categories": body.categories, "status": body.status},
    )
    return {"id": str(vendor_id), "status": "created"}


@router.put("/vendors/{vendor_id}")
async def update_vendor(
    vendor_id: UUID,
    body: VendorIn,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    _require_admin(auth)
    if body.status not in VENDOR_STATUSES:
        raise HTTPException(422, detail={"code": "VENDOR_STATUS_UNSUPPORTED"})
    if any(_category(category) != category for category in body.categories):
        raise HTTPException(422, detail={"code": "VENDOR_CATEGORY_UNSUPPORTED"})
    tenant_id = _tenant(auth)
    try:
        result = await session.execute(
            text(
                """UPDATE maintenance_vendors SET name=:name,nit=:nit,
                   categories=:categories,status=:status,
                   documents_valid_until=:documents_until,rating=:rating,
                   updated_by=:actor,updated_at=now(),version=version+1
                   WHERE tenant_id=:tenant AND id=:vendor"""
            ),
            {
                "tenant": tenant_id,
                "vendor": vendor_id,
                "name": body.name.strip(),
                "nit": body.nit.strip(),
                "categories": sorted(set(body.categories)),
                "status": body.status,
                "documents_until": body.documents_valid_until,
                "rating": body.rating,
                "actor": _actor(auth),
            },
        )
    except IntegrityError as exc:
        raise HTTPException(409, detail={"code": "VENDOR_NIT_ALREADY_EXISTS"}) from exc
    if result.rowcount == 0:
        raise HTTPException(404, detail={"code": "VENDOR_NOT_FOUND"})
    await _write_audit(
        session,
        tenant_id,
        _actor(auth),
        "maintenance.vendor.updated",
        "MaintenanceVendor",
        vendor_id,
        {"nit": body.nit, "categories": body.categories, "status": body.status},
    )
    return {"id": str(vendor_id), "status": "updated"}


def _order_select() -> str:
    return """
        SELECT o.id,o.code,o.title,o.description,o.category,o.severity,o.status,
               o.property_id,o.unit_id,o.asset_node_id,
               COALESCE(o.area_name,p.name,'') AS area_name,
               COALESCE(o.zone_name,n.name,u.name,'') AS zone_name,
               o.resident_id,o.vendor_id,v.name AS vendor_name,o.cost_cop,o.sla_due_at,
               o.reporter_kind,o.reporter_name,o.requested_by,o.approved_by,
               o.approved_at,o.approval_note,o.created_at,o.updated_at,o.version
        FROM maintenance_orders o
        LEFT JOIN managed_properties p
          ON p.tenant_id=o.tenant_id AND p.id=o.property_id
        LEFT JOIN managed_units u
          ON u.tenant_id=o.tenant_id AND u.id=o.unit_id
        LEFT JOIN twin_nodes n
          ON n.tenant_id=o.tenant_id AND n.id=o.asset_node_id
        LEFT JOIN maintenance_vendors v
          ON v.tenant_id=o.tenant_id AND v.id=o.vendor_id
        WHERE o.tenant_id=:tenant
    """


@router.get("/orders")
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = Query(default=None, max_length=24),
    category: str | None = Query(default=None, max_length=48),
    q: str | None = Query(default=None, max_length=160),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    _require_manager(auth)
    query = _order_select()
    params: dict[str, Any] = {"tenant": _tenant(auth)}
    if status:
        if status not in ORDER_STATUSES:
            raise HTTPException(422, detail={"code": "ORDER_STATUS_UNSUPPORTED"})
        query += " AND o.status=:status"
        params["status"] = status
    if category:
        query += " AND o.category=:category"
        params["category"] = _category(category)
    if q:
        query += """ AND (o.code ILIKE :q OR o.title ILIKE :q OR
                       o.description ILIKE :q OR o.reporter_name ILIKE :q)"""
        params["q"] = f"%{q}%"
    if date_from:
        query += " AND o.created_at>=:date_from"
        params["date_from"] = date_from
    if date_to:
        query += " AND o.created_at<(:date_to + INTERVAL '1 day')"
        params["date_to"] = date_to

    count_sql = f"SELECT count(*) FROM ({query}) orders"
    total = int(await session.scalar(text(count_sql), params) or 0)
    params.update({"limit": page_size, "offset": (page - 1) * page_size})
    rows = (
        await session.execute(
            text(query + " ORDER BY o.created_at DESC,o.id LIMIT :limit OFFSET :offset"),
            params,
        )
    ).mappings().all()
    return {
        "items": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/orders", status_code=201)
async def create_order(
    body: OrderIn,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = _tenant(auth)
    actor_id = _actor(auth)
    category = _category(body.category)
    manager = bool(MANAGER_ROLES.intersection(auth.roles))

    reporter = (
        await session.execute(
            text(
                """SELECT u.email,r.id AS resident_id,r.full_name
                   FROM users u LEFT JOIN maintenance_residents r
                     ON r.tenant_id=u.tenant_id AND r.user_id=u.id AND r.active
                   WHERE u.tenant_id=:tenant AND u.id=:actor AND u.is_active"""
            ),
            {"tenant": tenant_id, "actor": actor_id},
        )
    ).mappings().first()
    if reporter is None:
        raise HTTPException(401, detail={"code": "ACTIVE_USER_REQUIRED"})

    resident_id = body.resident_id
    if not manager:
        resident_id = reporter["resident_id"]
        if resident_id is None:
            raise HTTPException(403, detail={"code": "RESIDENT_PROFILE_REQUIRED"})
        if body.unit_id is not None:
            has_unit_access = await session.scalar(
                text(
                    """SELECT EXISTS (
                       SELECT 1 FROM maintenance_resident_units
                       WHERE tenant_id=:tenant AND resident_id=:resident
                         AND unit_id=:unit AND valid_from<=CURRENT_DATE
                         AND (valid_until IS NULL OR valid_until>=CURRENT_DATE)
                    )"""
                ),
                {
                    "tenant": tenant_id,
                    "resident": resident_id,
                    "unit": body.unit_id,
                },
            )
            if not has_unit_access:
                raise HTTPException(403, detail={"code": "RESIDENT_UNIT_NOT_ASSIGNED"})
        elif body.property_id is not None:
            has_property_access = await session.scalar(
                text(
                    """SELECT EXISTS (
                       SELECT 1
                       FROM maintenance_resident_units ru
                       JOIN managed_units mu
                         ON mu.tenant_id=ru.tenant_id AND mu.id=ru.unit_id
                       WHERE ru.tenant_id=:tenant AND ru.resident_id=:resident
                         AND mu.property_id=:property
                         AND ru.valid_from<=CURRENT_DATE
                         AND (ru.valid_until IS NULL OR ru.valid_until>=CURRENT_DATE)
                    )"""
                ),
                {
                    "tenant": tenant_id,
                    "resident": resident_id,
                    "property": body.property_id,
                },
            )
            if not has_property_access:
                raise HTTPException(403, detail={"code": "RESIDENT_PROPERTY_NOT_ASSIGNED"})
    resident_reporter_name = None
    if manager and resident_id is not None:
        resident_reporter_name = await session.scalar(
            text(
                "SELECT full_name FROM maintenance_residents "
                "WHERE tenant_id=:tenant AND id=:resident AND active"
            ),
            {"tenant": tenant_id, "resident": resident_id},
        )
        if resident_reporter_name is None:
            raise HTTPException(422, detail={"code": "RESIDENT_NOT_FOUND_OR_INACTIVE"})

    property_id = body.property_id
    area_name = ""
    zone_name = ""
    if body.unit_id is not None:
        unit = (
            await session.execute(
                text(
                    """SELECT mu.property_id,mu.name,mp.name AS property_name
                       FROM managed_units mu
                       JOIN managed_properties mp
                         ON mp.tenant_id=mu.tenant_id AND mp.id=mu.property_id
                       WHERE mu.tenant_id=:tenant AND mu.id=:unit"""
                ),
                {"tenant": tenant_id, "unit": body.unit_id},
            )
        ).mappings().first()
        if unit is None:
            raise HTTPException(422, detail={"code": "ORDER_UNIT_NOT_FOUND"})
        if property_id is not None and property_id != unit["property_id"]:
            raise HTTPException(422, detail={"code": "ORDER_UNIT_PROPERTY_MISMATCH"})
        property_id = unit["property_id"]
        area_name = unit["property_name"]
        zone_name = unit["name"]
    if property_id is not None:
        property_exists = await session.scalar(
            text("SELECT id FROM managed_properties WHERE tenant_id=:tenant AND id=:property"),
            {"tenant": tenant_id, "property": property_id},
        )
        if property_exists is None:
            raise HTTPException(422, detail={"code": "ORDER_PROPERTY_NOT_FOUND"})
        if not area_name:
            area_name = await session.scalar(
                text("SELECT name FROM managed_properties WHERE tenant_id=:tenant AND id=:property"),
                {"tenant": tenant_id, "property": property_id},
            ) or ""
    if body.asset_node_id is not None:
        asset = (
            await session.execute(
                text(
                    "SELECT name FROM twin_nodes WHERE tenant_id=:tenant AND id=:asset"
                ),
                {"tenant": tenant_id, "asset": body.asset_node_id},
            )
        ).scalar_one_or_none()
        if asset is None:
            raise HTTPException(422, detail={"code": "ORDER_ASSET_NOT_FOUND"})
        if not zone_name:
            zone_name = asset
    if body.vendor_id is not None:
        vendor = (
            await session.execute(
                text(
                    """SELECT categories FROM maintenance_vendors
                       WHERE tenant_id=:tenant AND id=:vendor AND status='active'"""
                ),
                {"tenant": tenant_id, "vendor": body.vendor_id},
            )
        ).scalar_one_or_none()
        if vendor is None:
            raise HTTPException(422, detail={"code": "ORDER_VENDOR_NOT_ACTIVE"})
        if vendor and category not in vendor:
            raise HTTPException(422, detail={"code": "VENDOR_CATEGORY_MISMATCH"})

    next_number = await session.scalar(
        text(
            """INSERT INTO maintenance_order_counters(tenant_id,last_number)
               VALUES(:tenant,1)
               ON CONFLICT(tenant_id) DO UPDATE
                 SET last_number=maintenance_order_counters.last_number+1
               RETURNING last_number"""
        ),
        {"tenant": tenant_id},
    )
    order_id = uuid4()
    reporter_kind = "resident" if resident_id is not None else "staff"
    reporter_name = (
        reporter["full_name"]
        if resident_id is not None and resident_id == reporter["resident_id"]
        else resident_reporter_name or reporter["email"]
    )
    status = "critical" if body.severity == "critical" else "pending_approval"
    result = await session.execute(
        text(
            """INSERT INTO maintenance_orders
               (id,tenant_id,code,title,description,category,severity,status,
                property_id,unit_id,asset_node_id,area_name,zone_name,resident_id,
                vendor_id,cost_cop,sla_due_at,reporter_kind,reporter_name,requested_by)
               VALUES(:id,:tenant,:code,:title,:description,:category,:severity,:status,
                :property,:unit,:asset,:area,:zone,:resident,:vendor,:cost,:sla,
                :reporter_kind,:reporter_name,:actor)
               RETURNING id"""
        ),
        {
            "id": order_id,
            "tenant": tenant_id,
            "code": f"MT-{int(next_number):08d}",
            "title": body.title.strip(),
            "description": body.description,
            "category": category,
            "severity": body.severity,
            "status": status,
            "property": property_id,
            "unit": body.unit_id,
            "asset": body.asset_node_id,
            "area": area_name,
            "zone": zone_name,
            "resident": resident_id,
            "vendor": body.vendor_id,
            "cost": body.cost_cop,
            "sla": body.sla_due_at,
            "reporter_kind": reporter_kind,
            "reporter_name": reporter_name,
            "actor": actor_id,
        },
    )
    result.scalar_one()
    await _record_order_event(
        session,
        tenant_id,
        order_id,
        actor_id,
        "created",
        None,
        status,
        {"category": category, "severity": body.severity},
    )
    await _write_audit(
        session,
        tenant_id,
        actor_id,
        "maintenance.order.created",
        "MaintenanceOrder",
        order_id,
        {"code": f"MT-{int(next_number):08d}", "status": status},
    )
    return {"id": str(order_id), "code": f"MT-{int(next_number):08d}", "status": status}


@router.get("/orders/mine")
async def list_my_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = Query(default=None, max_length=24),
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = _tenant(auth)
    query = _order_select() + """ AND (
        o.requested_by=:actor OR EXISTS (
            SELECT 1 FROM maintenance_residents r
            WHERE r.tenant_id=o.tenant_id AND r.id=o.resident_id
              AND r.user_id=:actor
        )
    )"""
    params: dict[str, Any] = {
        "tenant": tenant_id,
        "actor": _actor(auth),
    }
    if status:
        if status not in ORDER_STATUSES:
            raise HTTPException(422, detail={"code": "ORDER_STATUS_UNSUPPORTED"})
        query += " AND o.status=:status"
        params["status"] = status
    total = int(
        await session.scalar(
            text(f"SELECT count(*) FROM ({query}) orders"),
            params,
        )
        or 0
    )
    params.update({"limit": page_size, "offset": (page - 1) * page_size})
    rows = (
        await session.execute(
            text(query + " ORDER BY o.created_at DESC,o.id LIMIT :limit OFFSET :offset"),
            params,
        )
    ).mappings().all()
    return {
        "items": [dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/orders/{order_id}")
async def get_order(
    order_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    _require_manager(auth)
    row = (
        await session.execute(
            text(_order_select() + " AND o.id=:order_id"),
            {"tenant": _tenant(auth), "order_id": order_id},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(404, detail={"code": "MAINTENANCE_ORDER_NOT_FOUND"})
    return dict(row)


@router.patch("/orders/{order_id}")
async def update_order(
    order_id: UUID,
    body: OrderUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    _require_manager(auth)
    tenant_id = _tenant(auth)
    actor_id = _actor(auth)
    current = (
        await session.execute(
            text(
                """SELECT status,version,category FROM maintenance_orders
                   WHERE tenant_id=:tenant AND id=:order FOR UPDATE"""
            ),
            {"tenant": tenant_id, "order": order_id},
        )
    ).mappings().first()
    if current is None:
        raise HTTPException(404, detail={"code": "MAINTENANCE_ORDER_NOT_FOUND"})
    if current["version"] != body.expected_version:
        raise HTTPException(409, detail={"code": "MAINTENANCE_ORDER_VERSION_CONFLICT"})
    updates = body.model_dump(exclude_unset=True)
    updates.pop("expected_version")
    if not updates:
        raise HTTPException(422, detail={"code": "MAINTENANCE_ORDER_NO_CHANGES"})
    if "vendor_id" in updates and updates["vendor_id"] is not None:
        categories = await session.scalar(
            text(
                """SELECT categories FROM maintenance_vendors
                   WHERE tenant_id=:tenant AND id=:vendor AND status='active'"""
            ),
            {"tenant": tenant_id, "vendor": updates["vendor_id"]},
        )
        if categories is None:
            raise HTTPException(422, detail={"code": "ORDER_VENDOR_NOT_ACTIVE"})
        if categories and current["category"] not in categories:
            raise HTTPException(422, detail={"code": "VENDOR_CATEGORY_MISMATCH"})

    assignments = [f"{key}=:{key}" for key in updates]
    updates.update(
        {
            "tenant": tenant_id,
            "order": order_id,
            "expected_version": body.expected_version,
        }
    )
    result = await session.execute(
        text(
            "UPDATE maintenance_orders SET "
            + ",".join(assignments)
            + ",updated_at=now(),version=version+1 "
            "WHERE tenant_id=:tenant AND id=:order AND version=:expected_version "
            "RETURNING version"
        ),
        updates,
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(409, detail={"code": "MAINTENANCE_ORDER_VERSION_CONFLICT"})
    await _record_order_event(
        session,
        tenant_id,
        order_id,
        actor_id,
        "details_updated",
        current["status"],
        current["status"],
        updates,
    )
    await _write_audit(
        session,
        tenant_id,
        actor_id,
        "maintenance.order.updated",
        "MaintenanceOrder",
        order_id,
        {key: value for key, value in updates.items() if key not in {"tenant", "order", "expected_version"}},
    )
    return {"id": str(order_id), "status": current["status"], "version": version}


@router.get("/orders/{order_id}/events")
async def list_order_events(
    order_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    _require_manager(auth)
    exists = await session.scalar(
        text(
            "SELECT id FROM maintenance_orders WHERE tenant_id=:tenant AND id=:order"
        ),
        {"tenant": _tenant(auth), "order": order_id},
    )
    if exists is None:
        raise HTTPException(404, detail={"code": "MAINTENANCE_ORDER_NOT_FOUND"})
    rows = (
        await session.execute(
            text(
                """SELECT id,actor_id,event_type,from_status,to_status,details,created_at
                   FROM maintenance_order_events
                   WHERE tenant_id=:tenant AND order_id=:order
                   ORDER BY created_at,id"""
            ),
            {"tenant": _tenant(auth), "order": order_id},
        )
    ).mappings().all()
    return [dict(row) for row in rows]


@router.post("/orders/{order_id}/approve")
async def approve_order(
    order_id: UUID,
    body: ApprovalIn,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    _require_manager(auth)
    tenant_id = _tenant(auth)
    actor_id = _actor(auth)
    row = (
        await session.execute(
            text(
                """SELECT status,version FROM maintenance_orders
                   WHERE tenant_id=:tenant AND id=:order FOR UPDATE"""
            ),
            {"tenant": tenant_id, "order": order_id},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(404, detail={"code": "MAINTENANCE_ORDER_NOT_FOUND"})
    if row["version"] != body.expected_version:
        raise HTTPException(409, detail={"code": "MAINTENANCE_ORDER_VERSION_CONFLICT"})
    if row["status"] not in {"pending_approval", "critical"}:
        raise HTTPException(409, detail={"code": "MAINTENANCE_ORDER_NOT_AWAITING_APPROVAL"})

    result = await session.execute(
        text(
            """UPDATE maintenance_orders SET status='scheduled',approved_by=:actor,
               approved_at=now(),approval_note=:note,updated_at=now(),version=version+1
               WHERE tenant_id=:tenant AND id=:order AND version=:version
               RETURNING status"""
        ),
        {
            "tenant": tenant_id,
            "order": order_id,
            "actor": actor_id,
            "note": body.note,
            "version": body.expected_version,
        },
    )
    status = result.scalar_one_or_none()
    if status is None:
        raise HTTPException(409, detail={"code": "MAINTENANCE_ORDER_VERSION_CONFLICT"})
    await _record_order_event(
        session,
        tenant_id,
        order_id,
        actor_id,
        "approved",
        row["status"],
        status,
        {"note": body.note},
    )
    await _write_audit(
        session,
        tenant_id,
        actor_id,
        "maintenance.order.approved",
        "MaintenanceOrder",
        order_id,
        {"from_status": row["status"], "to_status": status, "note": body.note},
    )
    return {"id": str(order_id), "status": status, "version": body.expected_version + 1}


@router.patch("/orders/{order_id}/status")
async def transition_order(
    order_id: UUID,
    body: OrderStatusIn,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_tenant_session),
):
    _require_manager(auth)
    if body.status not in ORDER_STATUSES:
        raise HTTPException(422, detail={"code": "ORDER_STATUS_UNSUPPORTED"})
    tenant_id = _tenant(auth)
    actor_id = _actor(auth)
    row = (
        await session.execute(
            text(
                """SELECT status,version FROM maintenance_orders
                   WHERE tenant_id=:tenant AND id=:order FOR UPDATE"""
            ),
            {"tenant": tenant_id, "order": order_id},
        )
    ).mappings().first()
    if row is None:
        raise HTTPException(404, detail={"code": "MAINTENANCE_ORDER_NOT_FOUND"})
    if row["version"] != body.expected_version:
        raise HTTPException(409, detail={"code": "MAINTENANCE_ORDER_VERSION_CONFLICT"})
    if body.status in {"pending_approval", "critical"}:
        raise HTTPException(409, detail={"code": "USE_APPROVAL_ENDPOINT"})
    if body.status not in ORDER_TRANSITIONS.get(row["status"], set()):
        raise HTTPException(
            409,
            detail={
                "code": "MAINTENANCE_ORDER_TRANSITION_NOT_ALLOWED",
                "from": row["status"],
                "to": body.status,
            },
        )

    result = await session.execute(
        text(
            """UPDATE maintenance_orders SET status=:status,updated_at=now(),version=version+1
               WHERE tenant_id=:tenant AND id=:order AND version=:version
               RETURNING status"""
        ),
        {
            "tenant": tenant_id,
            "order": order_id,
            "status": body.status,
            "version": body.expected_version,
        },
    )
    status = result.scalar_one_or_none()
    if status is None:
        raise HTTPException(409, detail={"code": "MAINTENANCE_ORDER_VERSION_CONFLICT"})
    await _record_order_event(
        session,
        tenant_id,
        order_id,
        actor_id,
        "status_changed",
        row["status"],
        status,
        {"note": body.note},
    )
    await _write_audit(
        session,
        tenant_id,
        actor_id,
        "maintenance.order.status_changed",
        "MaintenanceOrder",
        order_id,
        {"from_status": row["status"], "to_status": status, "note": body.note},
    )
    return {"id": str(order_id), "status": status, "version": body.expected_version + 1}
