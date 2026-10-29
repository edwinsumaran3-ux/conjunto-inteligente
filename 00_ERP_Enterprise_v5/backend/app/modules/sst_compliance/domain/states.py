"""Estados de requisito y regla de avance (spec §4). Falla segura: lo desconocido nunca avanza."""
from __future__ import annotations
from enum import Enum


class RequirementStatus(str, Enum):
    NO_EVALUADO = "no_evaluado"
    PENDIENTE = "pendiente"
    EN_REVISION = "en_revision"
    CUMPLE = "cumple"
    NO_CUMPLE = "no_cumple"
    VENCIDO = "vencido"
    DESCONOCIDO = "desconocido"
    NO_APLICA = "no_aplica"
    EXCEPCION = "excepcion"


class Severity(str, Enum):
    CRITICO = "critico"
    ALTO = "alto"
    MEDIO = "medio"
    BAJO = "bajo"


# Solo estos estados permiten avanzar. Todo lo demás bloquea si el requisito es obligatorio.
ADVANCING = frozenset({RequirementStatus.CUMPLE, RequirementStatus.NO_APLICA, RequirementStatus.EXCEPCION})


def can_advance(status: RequirementStatus, mandatory: bool = True) -> bool:
    return (not mandatory) or status in ADVANCING
