"""Motor de requisitos determinista y fail-closed (spec §4).

Corrige defectos del borrador NestJS: la evidencia se busca por ALCANCE (zona/contratista/activo),
exige vigencia durante TODA la actividad, trata la ausencia de fecha de vencimiento como
'desconocido', evalúa horarios en la zona horaria de la organización y es idempotente
(una fila por requisito, no por reevaluación).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo
from .states import ADVANCING, RequirementStatus as S, Severity


class RulesEngineError(ValueError):
    pass


class NoApplicableRules(RulesEngineError):
    """Sin reglas aprobadas vigentes: estado desconocido, no se puede avanzar."""


@dataclass(frozen=True, slots=True)
class ActivityContext:
    activity_id: str
    activity_type: str
    jurisdiction: str
    risk_level: str
    zone_id: str
    start_at: datetime
    end_at: datetime
    timezone: str = "America/Bogota"
    aforo: int | None = None
    contractor_id: str | None = None
    asset_id: str | None = None
    requester_id: str | None = None

    def __post_init__(self) -> None:
        for n in ("start_at", "end_at"):
            v = getattr(self, n)
            if v.tzinfo is None:
                raise RulesEngineError(f"{n} debe incluir zona horaria")
        if self.end_at <= self.start_at:
            raise RulesEngineError("end_at debe ser posterior a start_at")


@dataclass(frozen=True, slots=True)
class RequirementResult:
    requirement_key: str
    rule_id: str
    rule_version: str
    status: S
    severity: Severity
    mandatory: bool
    reason: str
    evidence_type: str | None = None
    evidence_id: str | None = None

    @property
    def blocks_start(self) -> bool:
        return self.mandatory and self.status not in ADVANCING


@dataclass(frozen=True, slots=True)
class Evaluation:
    activity_id: str
    results: tuple[RequirementResult, ...]
    rules_used: tuple[tuple[str, str], ...]

    @property
    def blockers(self) -> tuple[RequirementResult, ...]:
        return tuple(r for r in self.results if r.blocks_start)

    @property
    def critical_blockers(self) -> tuple[RequirementResult, ...]:
        return tuple(r for r in self.blockers if r.severity is Severity.CRITICO)

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.results:
            out[r.status.value] = out.get(r.status.value, 0) + 1
        return out


def _tri_condition(cond: Mapping[str, Any] | None, ctx: ActivityContext) -> bool | None:
    """True=aplica, False=no aplica, None=indeterminado (dato faltante)."""
    if not cond:
        return True
    unknown = False
    if "aforo_min" in cond or "aforo_max" in cond:
        if ctx.aforo is None:
            unknown = True
        else:
            if "aforo_min" in cond and ctx.aforo < cond["aforo_min"]:
                return False
            if "aforo_max" in cond and ctx.aforo > cond["aforo_max"]:
                return False
    if "risk_levels" in cond and ctx.risk_level not in cond["risk_levels"]:
        return False
    if "requires_contractor" in cond and bool(cond["requires_contractor"]) != (ctx.contractor_id is not None):
        return False
    tw = cond.get("time_window")
    if tw:
        local = ctx.start_at.astimezone(ZoneInfo(ctx.timezone))
        h = local.hour + local.minute / 60
        a, b = float(tw["from"]), float(tw["to"])
        inside = (a <= h < b) if a <= b else (h >= a or h < b)  # ventana nocturna
        if not inside:
            return False
    return None if unknown else True


def _scope_matches(ev: Mapping[str, Any], scope: str, ctx: ActivityContext) -> bool:
    kind, sid = ev.get("scope_kind"), ev.get("scope_id")
    if scope == "organization":
        return kind == "organization"
    expected = {"zone": ctx.zone_id, "contractor": ctx.contractor_id, "asset": ctx.asset_id}.get(scope)
    return expected is not None and kind == scope and sid == expected


def _effective_expiry(ev: Mapping[str, Any], req: Mapping[str, Any]) -> datetime | None:
    if ev.get("expires_at") is not None:
        return ev["expires_at"]
    if req.get("max_age_days") and ev.get("issued_at") is not None:
        return ev["issued_at"] + timedelta(days=int(req["max_age_days"]))
    return None


class RulesEngine:
    """Evalúa requisitos. No toca BD: recibe reglas, evidencias y excepciones ya cargadas."""

    def select_rules(self, rules: Iterable[Mapping[str, Any]], ctx: ActivityContext) -> list[Mapping[str, Any]]:
        best: dict[str, Mapping[str, Any]] = {}
        for r in rules:
            if not r.get("approved_by"):
                continue  # regla sin aprobador humano no existe para el motor
            if r["jurisdiction"] != ctx.jurisdiction or r["activity_type"] != ctx.activity_type:
                continue
            if r["effective_from"] > ctx.start_at:
                continue
            if r.get("expires_at") is not None and r["expires_at"] < ctx.end_at:
                continue
            key = r["rule_key"]
            if key not in best or r["effective_from"] > best[key]["effective_from"]:
                best[key] = r
        return sorted(best.values(), key=lambda r: r["rule_key"])

    def evaluate(
        self,
        ctx: ActivityContext,
        rules: Sequence[Mapping[str, Any]],
        evidence: Sequence[Mapping[str, Any]],
        exceptions: Sequence[Mapping[str, Any]] = (),
        now: datetime | None = None,
    ) -> Evaluation:
        selected = self.select_rules(rules, ctx)
        if not selected:
            raise NoApplicableRules("No hay reglas aprobadas vigentes para esta actividad: estado desconocido")
        results: dict[str, RequirementResult] = {}
        for rule in selected:
            for req in rule["definition"].get("requirements", []):
                res = self._one(rule, req, ctx, evidence, exceptions, now)
                prev = results.get(req["key"])
                # Mismo requisito en dos reglas: gana el resultado más restrictivo.
                if prev is None or (res.blocks_start and not prev.blocks_start):
                    results[req["key"]] = res
        return Evaluation(ctx.activity_id, tuple(results[k] for k in sorted(results)),
                          tuple((r["rule_key"], r["version"]) for r in selected))

    def _one(self, rule, req, ctx, evidence, exceptions, now) -> RequirementResult:
        sev = Severity(req.get("severity", "alto"))
        mand = bool(req.get("mandatory", True))
        base = dict(requirement_key=req["key"], rule_id=str(rule["id"]), rule_version=str(rule["version"]),
                    severity=sev, mandatory=mand, evidence_type=req.get("evidence_type"))
        applies = _tri_condition(req.get("condition"), ctx)
        if applies is None:
            return RequirementResult(status=S.DESCONOCIDO, reason="Faltan datos para decidir aplicabilidad", **base)
        if applies is False:
            return RequirementResult(status=S.NO_APLICA, reason="Condición de aplicabilidad no cumplida", **base)

        exc = self._exception(req, exceptions, ctx, now or ctx.start_at)
        scope = req.get("scope", "zone")
        etype = req.get("evidence_type")
        if not etype:
            return RequirementResult(status=S.NO_EVALUADO, reason="Requisito sin tipo de evidencia definido", **base)
        if scope in ("contractor", "asset") and (ctx.contractor_id if scope == "contractor" else ctx.asset_id) is None:
            return RequirementResult(status=S.DESCONOCIDO, reason=f"Falta identificar {scope} de la actividad", **base)

        cands = [e for e in evidence if e.get("type") == etype and _scope_matches(e, scope, ctx)
                 and e.get("status") != "revoked"]
        if not cands:
            if exc:
                return RequirementResult(status=S.EXCEPCION, reason=f"Excepción aprobada {exc['approval_id']}", **base)
            return RequirementResult(status=S.PENDIENTE, reason="Evidencia no encontrada para el alcance", **base)

        verdicts = [self._judge(e, req, ctx) for e in cands]
        order = [S.CUMPLE, S.EN_REVISION, S.VENCIDO, S.DESCONOCIDO, S.NO_CUMPLE]
        verdicts.sort(key=lambda v: order.index(v[0]))
        status, reason, ev = verdicts[0]
        if status is not S.CUMPLE and exc:
            return RequirementResult(status=S.EXCEPCION, reason=f"Excepción aprobada {exc['approval_id']}",
                                     evidence_id=str(ev["id"]), **base)
        return RequirementResult(status=status, reason=reason, evidence_id=str(ev["id"]), **base)

    def _judge(self, ev, req, ctx):
        if ev.get("status") == "rejected":
            return (S.NO_CUMPLE, "Evidencia rechazada por el revisor", ev)
        exp = _effective_expiry(ev, req)
        if exp is None:
            if req.get("expiry_required", True):
                return (S.DESCONOCIDO, "La evidencia no declara vigencia", ev)
        elif exp < ctx.end_at:
            when = "antes de iniciar" if exp < ctx.start_at else "durante la actividad"
            return (S.VENCIDO, f"Evidencia vence {when} ({exp.isoformat()})", ev)
        if req.get("requires_review", False):
            rb = ev.get("reviewed_by")
            if not rb or ev.get("reviewed_at") is None:
                return (S.EN_REVISION, "Requiere verificación de persona competente", ev)
            if rb == ev.get("uploaded_by"):
                return (S.EN_REVISION, "El revisor no puede ser quien cargó la evidencia", ev)
        return (S.CUMPLE, "Evidencia vigente y verificada", ev)

    def _exception(self, req, exceptions, ctx, now):
        if not req.get("allows_exception", False):
            return None  # la norma no admite excepción
        for x in exceptions:
            if x.get("requirement_key") != req["key"] or not x.get("approval_id") or not x.get("approved_by"):
                continue
            if x["approved_by"] == ctx.requester_id:
                continue  # sin autoaprobación
            if x.get("expires_at") is not None and x["expires_at"] < ctx.end_at:
                continue
            return x
        return None
