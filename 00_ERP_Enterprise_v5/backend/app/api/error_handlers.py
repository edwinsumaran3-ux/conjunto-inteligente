"""Mapea errores de negocio/BD a respuestas HTTP controladas (antes escapaban como 500 genéricos)."""
from __future__ import annotations
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, IntegrityError
from backend.app.core.exceptions import ApplicationError, AuthenticationError, AuthorizationError, ConflictError

log = logging.getLogger("erp.errors")

def _sqlstate(exc: DBAPIError) -> str | None:
    o = getattr(exc, "orig", None)
    return getattr(o, "sqlstate", None) or getattr(getattr(o, "__cause__", None), "sqlstate", None)

def _msg(exc: BaseException) -> str:
    o = getattr(exc, "orig", None); cause = getattr(o, "__cause__", None)
    text = str(cause or o or exc).strip().splitlines()[0] if (cause or o or exc) else ""
    return text[:300]

def _resp(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": {"code": code, "message": message}})

def install(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def _app_err(_: Request, exc: ApplicationError):
        status = 401 if isinstance(exc, AuthenticationError) else 403 if isinstance(exc, AuthorizationError) else 409 if isinstance(exc, ConflictError) else 400
        return _resp(status, exc.code, str(exc))

    @app.exception_handler(LookupError)           # NotFound(LookupError) de SST y similares
    async def _lookup(_: Request, exc: LookupError):
        if type(exc).__module__.startswith(("sqlalchemy", "asyncpg", "builtins")) and not isinstance(exc, FileNotFoundError):
            raise exc          # KeyError/NoSuchColumnError son BUGS (p. ej. columna faltante), no "no encontrado": que se vean como 500
        return _resp(404, "NOT_FOUND", str(exc))

    @app.exception_handler(ValueError)            # reglas de negocio; los *NotFoundError (ValueError) -> 404
    async def _value(_: Request, exc: ValueError):
        if type(exc).__name__.endswith("NotFoundError"): return _resp(404, "NOT_FOUND", str(exc))
        return _resp(422, "BUSINESS_RULE_VIOLATION", str(exc))

    @app.exception_handler(RuntimeError)          # solo condiciones operativas conocidas; el resto sigue siendo 500 real
    async def _runtime(_: Request, exc: RuntimeError):
        m = str(exc).lower()
        if "in progress" in m or "idempotency" in m: return _resp(409, "IDEMPOTENCY_IN_PROGRESS", str(exc))
        if "not configured" in m: return _resp(422, "NOT_CONFIGURED", str(exc))
        raise exc

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError):
        return _resp(409, "INTEGRITY_CONFLICT", _msg(exc))

    @app.exception_handler(DBAPIError)
    async def _dbapi(_: Request, exc: DBAPIError):
        st = _sqlstate(exc)
        if st == "42501": return _resp(403, "FORBIDDEN", _msg(exc))
        if st in ("P0001", "23514", "22023", "22P02", "22007", "22003"): return _resp(422, "BUSINESS_RULE_VIOLATION", _msg(exc))   # RAISE EXCEPTION / CHECK / entrada inválida
        if st and st.startswith("23"): return _resp(409, "INTEGRITY_CONFLICT", _msg(exc))
        log.exception("database error sqlstate=%s", st); raise exc
