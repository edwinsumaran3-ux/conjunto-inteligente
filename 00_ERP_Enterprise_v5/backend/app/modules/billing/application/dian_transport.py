"""Puerto de transporte DIAN (ver DIAN_INTEGRATION_BOUNDARY.md). El sistema NO valida una factura sin un transporte real configurado.
Configuración: DIAN_TRANSPORT_ADAPTER="paquete.modulo:Clase" (clase sin argumentos con `async def submit(self, document) -> DianResponse`) o set_transport() desde código."""
from __future__ import annotations
import importlib, os
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from fastapi import HTTPException

@dataclass(frozen=True)
class DianResponse:
    outcome: str                      # ACCEPTED | REJECTED
    response_code: str
    response_description: str
    response_hash: str                # hash del acuse/respuesta firmada (obligatorio)
    external_id: str | None = None    # CUFE/CUDE o identificador asignado

class DianTransport(Protocol):
    async def submit(self, document: Mapping[str, Any]) -> DianResponse: ...

_custom: DianTransport | None = None
def set_transport(t: DianTransport | None) -> None:
    global _custom; _custom = t

def get_transport() -> DianTransport:
    if _custom is not None: return _custom
    spec = os.getenv("DIAN_TRANSPORT_ADAPTER")
    if not spec or ":" not in spec: raise HTTPException(503, {"code": "DIAN_TRANSPORT_NOT_CONFIGURED"})   # bloqueo explícito, nunca una aceptación simulada
    mod, cls = spec.split(":", 1)
    try: return getattr(importlib.import_module(mod), cls)()
    except Exception as e: raise HTTPException(503, {"code": "DIAN_TRANSPORT_LOAD_FAILED", "detail": type(e).__name__}) from e

def validate_response(r: DianResponse) -> DianResponse:
    if r.outcome not in ("ACCEPTED", "REJECTED"): raise HTTPException(502, {"code": "DIAN_RESPONSE_INVALID_OUTCOME"})
    if not r.response_hash or len(r.response_hash) < 16: raise HTTPException(502, {"code": "DIAN_RESPONSE_UNVERIFIED"})   # sin hash del acuse no hay validación
    if r.outcome == "ACCEPTED" and not r.external_id: raise HTTPException(502, {"code": "DIAN_ACCEPTED_WITHOUT_ID"})        # aceptada sin CUFE/CUDE: inválida
    return r
