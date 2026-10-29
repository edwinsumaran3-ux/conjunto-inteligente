"""Matriz de autoridad (spec §8). Determinista, sin autoaprobación, falla segura."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Sequence


class AuthorityError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class AuthorityResolution:
    primary_id: str
    backup_id: str | None
    approver_role: str
    requires_mfa: bool
    reason: str


def _amt(v: Any) -> Decimal | None:
    return None if v is None else Decimal(str(v))


def _matches(rule: Mapping[str, Any], request_type: str, risk: str, amount: Decimal | None) -> bool:
    if rule["request_type"] != request_type:
        return False
    if risk not in rule.get("risk_levels", []):
        return False
    lo, hi = _amt(rule.get("min_amount")), _amt(rule.get("max_amount"))
    if lo is None and hi is None:
        return True  # regla sin cuantía (p. ej. permiso de trabajo)
    if amount is None:
        return False  # regla por cuantía y no se informó monto: no se adivina
    return (lo is None or amount >= lo) and (hi is None or amount < hi)  # [lo, hi)


def resolve(
    matrix: Mapping[str, Any] | None,
    *,
    request_type: str,
    risk_level: str,
    requester_id: str,
    users: Sequence[Mapping[str, Any]],
    amount: Any = None,
) -> AuthorityResolution:
    if not matrix or not matrix.get("rules"):
        raise AuthorityError("La organización no tiene matriz de autoridad aprobada")
    amt = _amt(amount)
    hits = [r for r in matrix["rules"] if _matches(r, request_type, risk_level, amt)]
    if not hits:
        raise AuthorityError(f"Sin regla de autoridad para {request_type}/{risk_level}")
    if len(hits) > 1:
        raise AuthorityError("Matriz ambigua: varias reglas aplican; debe corregirla un administrador")
    rule = hits[0]
    role = rule["approver_role"]
    cands = sorted(
        (u for u in users
         if u.get("active", True) and role in u.get("roles", ())
         and u["id"] != requester_id and requester_id not in u.get("conflicts", ())),
        key=lambda u: str(u["id"]),
    )
    if not cands:
        raise AuthorityError(f"No hay aprobador elegible con rol {role} (sin autoaprobación ni conflicto)")
    mfa = bool(rule.get("requires_mfa", False)) or risk_level == "critico" or (
        matrix.get("mfa_amount_threshold") is not None and amt is not None
        and amt >= _amt(matrix["mfa_amount_threshold"]))
    return AuthorityResolution(str(cands[0]["id"]), str(cands[1]["id"]) if len(cands) > 1 else None,
                               role, mfa, f"Matriz de autoridad: {role} para {request_type}")
