"""Guarda de arranque: la API NO debe conectar con un rol que ignora RLS (superusuario / BYPASSRLS). Con uno, PostgreSQL no aplica las políticas por tenant."""
from __future__ import annotations
import logging
from sqlalchemy import text
log = logging.getLogger("erp.rls")

async def assert_rls_effective(engine, *, production: bool) -> bool:
    async with engine.connect() as c:
        row = (await c.execute(text("SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"))).one()
    unsafe = bool(row.rolsuper or row.rolbypassrls)
    if unsafe:
        msg = f"el rol de base de datos '{row.rolname}' es superusuario/BYPASSRLS: las políticas por tenant (RLS) NO se aplican"
        if production: raise RuntimeError("ARRANQUE RECHAZADO: " + msg)
        log.warning("ADVERTENCIA: %s (solo tolerable en desarrollo)", msg)
    return not unsafe
