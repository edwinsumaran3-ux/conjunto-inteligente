"""Política de fallos para consumidores RabbitMQ (solo biblioteca estándar).

Problema que resuelve: con `msg.process(requeue=True)` un mensaje que SIEMPRE
falla (JSON corrupto, campo ausente, violación de constraint) se reencola sin
fin y bloquea la cola a máxima velocidad.

Política:
  * Error permanente (datos inválidos / SQLSTATE 22xxx, 23xxx)  -> dead-letter inmediato.
  * Error transitorio (BD/red caídas)                           -> 1 reintento; si vuelve a
    fallar (`redelivered=True`) -> dead-letter.
  * Si no se puede PERSISTIR el dead-letter (BD caída) el mensaje se reencola: nunca se pierde.

CANÓNICO: shared/libs/resilience.py. Se copia tal cual a cada servicio
(sus imágenes Docker se construyen con contexto propio); una prueba verifica
que las copias no diverjan.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Awaitable, Callable

log = logging.getLogger("resilience")

PERMANENT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    json.JSONDecodeError, UnicodeDecodeError, KeyError, ValueError, TypeError, AttributeError,
)


def is_permanent_error(exc: BaseException) -> bool:
    """True si reintentar no puede arreglar el fallo."""
    if isinstance(exc, PERMANENT_EXCEPTIONS):
        return True
    sqlstate = getattr(exc, "sqlstate", None)
    # 22xxx = data exception, 23xxx = integrity constraint violation
    return isinstance(sqlstate, str) and sqlstate[:2] in ("22", "23")


def _body_text(body: Any) -> str:
    if isinstance(body, (bytes, bytearray)):
        return bytes(body).decode("utf-8", errors="replace")
    return str(body)


async def record_dead_letter(pool: Any, *, service: str, queue: str, msg: Any, exc: BaseException) -> bool:
    """Persiste el mensaje fallido. Devuelve False si no pudo guardarse."""
    if pool is None:
        return False
    raw = msg.body if isinstance(msg.body, (bytes, bytearray)) else _body_text(msg.body).encode("utf-8")
    try:
        headers = json.dumps(dict(getattr(msg, "headers", None) or {}), default=str)
        async with pool.acquire() as c:
            await c.execute(
                """INSERT INTO dead_letter_messages
                   (source_service,queue_name,message_id,headers,body,body_sha256,error_class,error_message,redelivered)
                   VALUES($1,$2,$3,$4::jsonb,$5,$6,$7,$8,$9)""",
                service, queue, getattr(msg, "message_id", None), headers, _body_text(msg.body)[:200_000],
                hashlib.sha256(raw).hexdigest(), type(exc).__name__, str(exc)[:2000],
                bool(getattr(msg, "redelivered", False)),
            )
        return True
    except Exception:  # noqa: BLE001
        log.exception("no se pudo persistir dead-letter (%s/%s)", service, queue)
        return False


async def handle_failure(msg: Any, exc: BaseException, *, pool: Any, service: str, queue: str,
                         requeue_delay_s: float = 1.0) -> str:
    """Aplica la política y devuelve 'dead-lettered' | 'requeued'."""
    permanent = is_permanent_error(exc)
    if permanent or getattr(msg, "redelivered", False):
        if await record_dead_letter(pool, service=service, queue=queue, msg=msg, exc=exc):
            log.error("mensaje a dead-letter (%s/%s, permanente=%s): %r", service, queue, permanent, exc)
            await msg.reject(requeue=False)
            return "dead-lettered"
        log.error("dead-letter no disponible: se reencola para no perder el mensaje (%s/%s): %r", service, queue, exc)
    else:
        log.warning("fallo transitorio, 1 reintento (%s/%s): %r", service, queue, exc)
    await asyncio.sleep(requeue_delay_s)
    await msg.nack(requeue=True)
    return "requeued"


async def process_message(msg: Any, handler: Callable[[Any], Awaitable[None]], *, pool: Any,
                          service: str, queue: str, requeue_delay_s: float = 1.0) -> str:
    """ack si `handler` termina bien; en otro caso aplica `handle_failure`."""
    try:
        await handler(msg)
    except asyncio.CancelledError:
        await msg.nack(requeue=True)
        raise
    except Exception as exc:  # noqa: BLE001
        return await handle_failure(msg, exc, pool=pool, service=service, queue=queue, requeue_delay_s=requeue_delay_s)
    await msg.ack()
    return "acked"
