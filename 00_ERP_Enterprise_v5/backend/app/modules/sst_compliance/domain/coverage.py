"""Cobertura temporal y asignaciones (spec §2 y §7). Mide CAPACIDAD, no cantidad de filas.
El sistema nunca decide la cantidad/tipo requerido: viene de una regla aprobada o queda 'desconocido'."""
from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Sequence


class CoverageError(PermissionError):
    def __init__(self, code: str, msg: str = ""):
        super().__init__(f"{code}: {msg}" if msg else code)
        self.code = code


class CoverageState(str, Enum):
    CUBIERTA = "cubierta"
    BRECHA = "brecha"
    DESCONOCIDA = "desconocida"


@dataclass(frozen=True, slots=True)
class CoverageResult:
    state: CoverageState
    required_units: float | None
    available_units: float
    gap: float | None
    counted: tuple[str, ...]
    excluded: tuple[tuple[str, str], ...]


def _overlaps(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> bool:
    return a0 < b1 and b0 < a1


def compute_coverage(*, zone_id: str, asset_type: str, required_units: float | None, start_at: datetime,
                     end_at: datetime, assets: Sequence[Mapping[str, Any]],
                     assignments: Sequence[Mapping[str, Any]], other_reservations: Sequence[Mapping[str, Any]] = ()) -> CoverageResult:
    counted: list[str] = []
    excluded: list[tuple[str, str]] = []
    total = 0.0
    assign_by_asset = {a["asset_id"]: a for a in assignments if a.get("zone_id") == zone_id}
    for a in assets:
        aid = str(a["id"])
        if a.get("asset_type") != asset_type:
            continue
        temp = aid in assign_by_asset
        if a.get("zone_id") != zone_id and not temp:
            continue
        if a.get("status") != "disponible":
            excluded.append((aid, f"estado {a.get('status') or 'desconocido'}")); continue
        exp = a.get("expires_at")
        if exp is not None and exp < end_at:
            excluded.append((aid, "vence antes de terminar la actividad")); continue
        ins = a.get("inspection_valid_until")
        if ins is None or ins < end_at:
            excluded.append((aid, "inspección ausente o vencida")); continue
        if temp:
            asg = assign_by_asset[aid]
            if asg.get("status") not in ("verified", "active"):
                excluded.append((aid, "asignación temporal sin verificación física")); continue
            if not (asg["start_at"] <= start_at and asg["end_at"] >= end_at):
                excluded.append((aid, "asignación no cubre toda la ventana")); continue
        if any(r.get("asset_id") == aid and r.get("activity_zone") != zone_id and
               _overlaps(r["start_at"], r["end_at"], start_at, end_at) for r in other_reservations):
            excluded.append((aid, "reservado en otra zona en la misma ventana")); continue
        cap = a.get("capacity_units")
        if cap is None or float(cap) <= 0:
            excluded.append((aid, "capacidad desconocida")); continue
        total += float(cap); counted.append(aid)
    if required_units is None:
        return CoverageResult(CoverageState.DESCONOCIDA, None, total, None, tuple(counted), tuple(excluded))
    gap = max(0.0, float(required_units) - total)
    return CoverageResult(CoverageState.CUBIERTA if gap == 0 else CoverageState.BRECHA,
                          float(required_units), total, gap, tuple(counted), tuple(excluded))


# --- Ciclo de vida de la asignación temporal (proposed → verified → active → returned) ---
@dataclass(frozen=True, slots=True)
class TemporaryAssignment:
    id: str
    activity_id: str
    asset_id: str
    zone_id: str
    start_at: datetime
    end_at: datetime
    responsible_id: str
    proposed_by: str
    status: str = "proposed"
    inspection_id: str | None = None
    verified_by: str | None = None


def propose(*, id: str, activity_id: str, asset_id: str, zone_id: str, start_at: datetime, end_at: datetime,
            responsible_id: str, proposed_by: str) -> TemporaryAssignment:
    if not zone_id:
        raise CoverageError("ZONE_REQUIRED", "la asignación debe indicar zona")
    if end_at <= start_at:
        raise CoverageError("WINDOW_INVALID")
    return TemporaryAssignment(id, activity_id, asset_id, zone_id, start_at, end_at, responsible_id, proposed_by)


def verify(a: TemporaryAssignment, *, verifier_id: str, inspection_id: str | None, physical_check_ok: bool) -> TemporaryAssignment:
    if a.status != "proposed":
        raise CoverageError("NOT_PROPOSED")
    if not inspection_id or not physical_check_ok:
        raise CoverageError("PHYSICAL_VERIFICATION_REQUIRED", "no basta con que el sistema diga que existe")
    if verifier_id == a.proposed_by:
        raise CoverageError("SELF_VERIFICATION", "quien propone no puede verificar")
    return replace(a, status="verified", inspection_id=inspection_id, verified_by=verifier_id)


def activate_assignment(a: TemporaryAssignment, now: datetime) -> TemporaryAssignment:
    if a.status != "verified":
        raise CoverageError("NOT_VERIFIED")
    if not (a.start_at <= now < a.end_at):
        raise CoverageError("OUTSIDE_WINDOW")
    return replace(a, status="active")


def return_assignment(a: TemporaryAssignment, *, return_inspection_ok: bool) -> TemporaryAssignment:
    if a.status != "active":
        raise CoverageError("NOT_ACTIVE")
    if not return_inspection_ok:
        raise CoverageError("RETURN_INSPECTION_REQUIRED")
    return replace(a, status="returned")


def asset_state_after_recharge_return(*, inspected_ok: bool) -> str:
    """Un extintor que vuelve de recarga NO pasa a disponible sin inspección."""
    return "disponible" if inspected_ok else "mantenimiento"
