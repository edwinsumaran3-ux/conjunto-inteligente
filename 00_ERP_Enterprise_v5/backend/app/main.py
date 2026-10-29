"""FastAPI application entry point for the ERP service."""
from __future__ import annotations
from contextlib import asynccontextmanager
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from backend.app.db.session import get_session_factory, dispose_engine
from backend.app.modules.auth.api import router as auth_router
from backend.app.modules.clinical.api.router import router as clinical_router
from backend.app.modules.inventory.api.router import router as inventory_router
from backend.app.modules.billing.api.router import router as billing_router
from backend.app.modules.sales.api.router import router as sales_router
from backend.app.modules.finance.api.router import router as finance_router
from backend.app.modules.digital_twin.api.router import router as digital_twin_router
from backend.app.modules.digital_twin.api.bim_router import router as digital_twin_bim_router
from backend.app.modules.estate.api.router import router as estate_router
from backend.app.modules.interaction.api.router import router as realtime_router
from backend.app.modules.sst_compliance.api.router import router as sst_router
from backend.app.modules.accounting.api.router import router as accounting_router
from backend.app.modules.agent_control.api.router import router as agent_control_router
from backend.app.modules.edge_fleet.api import router as edge_fleet_router
from backend.app.modules.edge_transport.api import router as edge_transport_router
from backend.app.modules.edge_trust.api import router as edge_trust_router
from backend.app.modules.physical_edge.api import router as physical_edge_router
from backend.app.modules.agent_execution.api import router as agent_execution_router
from backend.app.modules.agent_memory.api import router as agent_memory_router
from backend.app.modules.intelligence_plane.api import router as intelligence_router
from backend.app.modules.ml_lifecycle.api import router as ml_lifecycle_router
from backend.app.modules.neural_inference.api import router as neural_router
from backend.app.modules.model_ops.api import router as model_ops_router
from backend.app.modules.config_admin.api import router as config_admin_router
from backend.app.modules.users.api import router as users_router
from backend.app.modules.mfa.api import router as mfa_router
from backend.app.modules.sst_compliance.api.master_router import router as sst_master_router
from backend.app.modules.maintenance.api import router as maintenance_router
from backend.app.modules.tenants.api import router as tenants_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lazy factory initialization validates DATABASE_URL without connecting yet.
    app.state.tenant_session_factory = get_session_factory()
    if os.getenv("APP_ENV", "development") == "production":
        from backend.app.db.rls_guard import assert_rls_effective
        from backend.app.db.session import get_engine
        await assert_rls_effective(get_engine(), production=True)      # rechaza arrancar con superusuario/BYPASSRLS
    try:
        yield
    finally:
        await dispose_engine()

app=FastAPI(title="Conjunto Inteligente ERP API", version="12.0.0", lifespan=lifespan)
from backend.app.api.error_handlers import install as _install_error_handlers
_install_error_handlers(app)
for router in (auth_router, clinical_router, inventory_router, billing_router, sales_router,
               finance_router, digital_twin_router, digital_twin_bim_router, estate_router, realtime_router, sst_router,
               accounting_router, agent_control_router, edge_fleet_router, edge_transport_router, edge_trust_router,
               physical_edge_router, agent_execution_router, agent_memory_router, intelligence_router, ml_lifecycle_router,
               neural_router, model_ops_router, config_admin_router, users_router, sst_master_router, mfa_router,
               maintenance_router, tenants_router):
    app.include_router(router, prefix="/api/v1")

_origins=[o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS","").split(",") if o.strip()]
if _origins:  # sin comodín: el visor BIM servido desde otro origen debe declararse explícitamente
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"], allow_headers=["Authorization","Content-Type"], max_age=600)

@app.middleware("http")
async def prevent_api_response_caching(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/v1/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response

_bim_dir=Path(os.getenv("BIM_STATIC_DIR", str(Path(__file__).resolve().parents[2]/"frontend"/"dist"/"bim")))
if _bim_dir.is_dir():  # mismo origen => sin CORS; el visor llama a /api/v1
    app.mount("/bim", StaticFiles(directory=str(_bim_dir), html=True), name="bim")

@app.get("/healthz", tags=["health"])
async def healthz():
    return {"status":"ok"}

@app.get("/readyz", tags=["health"])
async def readyz():
    required_tables = ("tenants", "users", "idempotency_records", "audit_log", "realtime_events",
                       "user_totp_credentials", "outbox_events", "edge_telemetry_ingest_limits",
                       "maintenance_residents", "maintenance_vendors", "maintenance_orders",
                       "maintenance_order_events")
    try:
        factory=get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
            checks = await session.execute(text("""SELECT
                to_regclass('public.tenants') IS NOT NULL AND
                to_regclass('public.users') IS NOT NULL AND
                to_regclass('public.idempotency_records') IS NOT NULL AND
                to_regclass('public.audit_log') IS NOT NULL AND
                to_regclass('public.realtime_events') IS NOT NULL AND
                to_regclass('public.user_totp_credentials') IS NOT NULL AND
                to_regclass('public.outbox_events') IS NOT NULL AND
                to_regclass('public.edge_telemetry_ingest_limits') IS NOT NULL AND
                to_regclass('public.maintenance_residents') IS NOT NULL AND
                to_regclass('public.maintenance_vendors') IS NOT NULL AND
                to_regclass('public.maintenance_orders') IS NOT NULL AND
                to_regclass('public.maintenance_order_events') IS NOT NULL"""))
            schema_ready = bool(checks.scalar_one())
    except Exception as exc:
        raise HTTPException(status_code=503,detail="Database is not ready") from exc
    if not schema_ready:
        raise HTTPException(status_code=503,detail={"status":"not_ready","reason":"required SQL migrations have not been applied",
                                                   "required_tables":list(required_tables)})
    return {"status":"ready","database":"ok","schema":"ok"}

_frontend_dir=Path(os.getenv("FRONTEND_STATIC_DIR", str(Path(__file__).resolve().parents[2]/"frontend"/"dist")))
if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
