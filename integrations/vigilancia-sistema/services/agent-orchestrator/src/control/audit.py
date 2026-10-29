from __future__ import annotations
import json
import logging
from typing import Any

log = logging.getLogger("audit")

ACTOR_TYPES = {"OPERATOR", "AGENT", "SYSTEM", "DEVICE", "LLM"}


class AuditLog:
    """Escritor de la auditoría append-only con cadena de hash (tabla `audit_log`, migración 0005).

    `record` NUNCA lanza: la auditoría fallida se registra en el log del proceso y devuelve False.
    Las rutas físicas (journal de comandos) son las que fallan cerrado; la auditoría de decisiones
    humanas es complementaria y no debe convertir un fallo de BD en una acción denegada a mitad de camino.
    """
    def __init__(self, pool):
        self.pool = pool

    async def record(self, *, actor: str, actor_type: str, action: str, entity_type: str | None = None,
                     entity_id: str | None = None, correlation_id: str | None = None,
                     details: dict[str, Any] | None = None, tenant_id: str = "default") -> bool:
        if actor_type not in ACTOR_TYPES:
            log.error("audit actor_type inválido: %s", actor_type)
            return False
        try:
            async with self.pool.acquire() as c:
                await c.execute(
                    """INSERT INTO audit_log(tenant_id,actor,actor_type,action,entity_type,entity_id,correlation_id,details)
                       VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb)""",
                    tenant_id, actor, actor_type, action, entity_type, entity_id, correlation_id,
                    json.dumps(details or {}, default=str),
                )
            return True
        except Exception:  # noqa: BLE001
            log.exception("no se pudo escribir audit_log (%s %s)", action, entity_id)
            return False
