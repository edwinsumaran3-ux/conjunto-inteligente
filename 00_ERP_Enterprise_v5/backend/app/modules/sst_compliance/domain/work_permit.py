"""ATS y permiso de trabajo (spec §6). Vinculado a tarea/zona/horario/personas/versión; expira solo."""
from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Mapping, Sequence


class PermitError(PermissionError):
    def __init__(self, code: str, msg: str = ""):
        super().__init__(f"{code}: {msg}" if msg else code)
        self.code = code


class PermitStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    CLOSED = "closed"


STEP_FIELDS = ("hazard", "consequence", "control", "responsible", "control_evidence")


def validate_ats(steps: Sequence[Mapping[str, Any]], signatures: Sequence[Mapping[str, Any]],
                 required_signers: Sequence[str]) -> list[str]:
    """Devuelve la lista de faltantes; vacía = ATS completo. No evalúa idoneidad técnica."""
    missing: list[str] = []
    if not steps:
        missing.append("ATS sin pasos")
    for i, s in enumerate(steps, 1):
        for f in STEP_FIELDS:
            if not str(s.get(f, "")).strip():
                missing.append(f"paso {i}: falta {f}")
    signed = {x.get("user_id") for x in signatures if x.get("signed_at")}
    for u in required_signers:
        if u not in signed:
            missing.append(f"falta firma de {u}")
    return missing


@dataclass(frozen=True, slots=True)
class WorkPermit:
    id: str
    activity_id: str
    ats_id: str
    ats_version: int
    permit_type: str
    zone_id: str
    contractor_id: str
    worker_ids: frozenset[str]
    valid_from: datetime
    valid_to: datetime
    status: PermitStatus = PermitStatus.PENDING
    approval_id: str | None = None

    def effective_status(self, now: datetime) -> PermitStatus:
        if self.status in (PermitStatus.ACTIVE, PermitStatus.PENDING) and now >= self.valid_to:
            return PermitStatus.EXPIRED
        return self.status

    def authorizes(self, *, now: datetime, zone_id: str, contractor_id: str, worker_id: str,
                   activity_id: str) -> bool:
        """Autoriza SOLO a esta tarea/zona/contratista/persona dentro de la ventana. Sin reutilización."""
        return (self.effective_status(now) is PermitStatus.ACTIVE and self.valid_from <= now < self.valid_to
                and self.activity_id == activity_id and self.zone_id == zone_id
                and self.contractor_id == contractor_id and worker_id in self.worker_ids)


def activate(p: WorkPermit, *, now: datetime, approval_granted: bool, evaluation_blocked: bool,
             ats_missing: Sequence[str], max_hours: int = 12) -> WorkPermit:
    if p.status is not PermitStatus.PENDING:
        raise PermitError("PERMIT_NOT_PENDING")
    if p.valid_to <= p.valid_from or p.valid_to - p.valid_from > timedelta(hours=max_hours):
        raise PermitError("PERMIT_WINDOW", f"ventana inválida o mayor a {max_hours} h")
    if now >= p.valid_to:
        raise PermitError("PERMIT_EXPIRED")
    if not p.worker_ids:
        raise PermitError("PERMIT_NO_WORKERS")
    if not approval_granted:
        raise PermitError("APPROVAL_REQUIRED", "sin aprobación vigente (el silencio no autoriza)")
    if evaluation_blocked:
        raise PermitError("CRITICAL_BLOCKER", "hay requisitos obligatorios sin cumplir")
    if ats_missing:
        raise PermitError("ATS_INCOMPLETE", "; ".join(ats_missing[:5]))
    return replace(p, status=PermitStatus.ACTIVE)


_MATERIAL = {"zone", "contractor", "risk", "scope", "ats_version", "workers", "schedule"}


def apply_change(p: WorkPermit, changed: set[str]) -> WorkPermit:
    """Un cambio material suspende el permiso; hay que reevaluar y reautorizar."""
    if p.status is PermitStatus.ACTIVE and changed & _MATERIAL:
        return replace(p, status=PermitStatus.SUSPENDED)
    return p


def close(p: WorkPermit, *, final_inspection_ok: bool, open_critical_risks: int, unreconciled_resources: int) -> WorkPermit:
    if not final_inspection_ok:
        raise PermitError("INSPECTION_REQUIRED")
    if open_critical_risks or unreconciled_resources:
        raise PermitError("CLOSE_BLOCKED", "riesgos críticos abiertos o recursos sin conciliar")
    return replace(p, status=PermitStatus.CLOSED)
