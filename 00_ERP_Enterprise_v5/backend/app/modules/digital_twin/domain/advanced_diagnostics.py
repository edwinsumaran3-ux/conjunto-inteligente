"""Advanced, auditable diagnostic primitives for the engineering digital twin.

No ML or causal certainty is claimed. These functions produce evidence-backed
hypotheses from synchronized telemetry features and explicit engineering rules.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
from statistics import median
from typing import Iterable, Sequence

@dataclass(frozen=True)
class ChangePoint:
    detected: bool
    magnitude: float
    before: float
    after: float
    direction: str
    evidence: dict

@dataclass(frozen=True)
class DiagnosticHypothesis:
    code: str
    confidence: float
    severity: str
    evidence: tuple[str, ...]
    recommended_actions: tuple[str, ...]


def _vals(values: Iterable[float]) -> list[float]:
    out = [float(v) for v in values if isfinite(float(v))]
    if len(out) < 4:
        raise ValueError("INSUFFICIENT_VALUES")
    return out


def normalized_change_point(values: Iterable[float], scale: float) -> ChangePoint:
    vals = _vals(values)
    if scale <= 0:
        raise ValueError("INVALID_SCALE")
    cut = len(vals) // 2
    before = median(vals[:cut])
    after = median(vals[cut:])
    magnitude = min(1.0, abs(after - before) / scale)
    direction = "up" if after > before else "down" if after < before else "flat"
    return ChangePoint(
        detected=magnitude >= 0.50,
        magnitude=round(magnitude, 6), before=before, after=after,
        direction=direction,
        evidence={"split_index": cut, "sample_count": len(vals), "scale": scale},
    )


def lagged_alignment(a: Sequence[float], b: Sequence[float], max_lag: int = 2) -> dict:
    if len(a) != len(b) or len(a) < 4:
        raise ValueError("ALIGNMENT_REQUIRES_EQUAL_SERIES")
    if max_lag < 0 or max_lag >= len(a):
        raise ValueError("INVALID_MAX_LAG")
    def corr(x: Sequence[float], y: Sequence[float]) -> float:
        mx, my = sum(x)/len(x), sum(y)/len(y)
        dx, dy = [v-mx for v in x], [v-my for v in y]
        den = (sum(v*v for v in dx)*sum(v*v for v in dy)) ** 0.5
        return 0.0 if den == 0 else sum(x*y for x,y in zip(dx,dy))/den
    candidates=[]
    for lag in range(-max_lag, max_lag+1):
        if lag < 0: x,y=a[-lag:],b[:len(b)+lag]
        elif lag > 0: x,y=a[:-lag],b[lag:]
        else: x,y=a,b
        candidates.append((abs(corr(x,y)), lag, corr(x,y)))
    score, lag, signed = max(candidates, key=lambda t:t[0])
    return {"correlation": round(signed,6), "absolute_correlation": round(score,6), "lag_samples": lag}


def build_hypotheses(features: Sequence[dict]) -> tuple[DiagnosticHypothesis, ...]:
    by_kind = {str(f["semantic_kind"]).lower(): f for f in features}
    out: list[DiagnosticHypothesis] = []
    def add(code: str, kinds: tuple[str,...], actions: tuple[str,...], base: float=.55):
        present=[by_kind[k] for k in kinds if k in by_kind]
        if len(present) != len(kinds): return
        impairment=sum(float(f["impairment"]) for f in present)/len(present)
        quality=sum(float(f.get("quality_penalty",0)) for f in present)/len(present)
        confidence=max(0.0,min(1.0, base + 0.35*impairment - 0.25*quality))
        severity="critical" if confidence>=.90 else "high" if confidence>=.75 else "medium" if confidence>=.50 else "low"
        evidence=tuple(str(f["point_id"]) for f in present)
        out.append(DiagnosticHypothesis(code,round(confidence,3),severity,evidence,actions))
    add("MECHANICAL_DEGRADATION",("temperature","vibration"),("Inspect bearings, alignment and lubrication.","Compare vibration spectrum before replacing components."))
    add("HYDRAULIC_RESTRICTION",("pressure","flow"),("Inspect filters, valves and restrictions.","Verify differential pressure against design envelope."))
    add("ELECTRICAL_THERMAL_STRESS",("power","temperature"),("Inspect electrical loading and cooling path.","Verify protection settings and thermal rise."))
    add("ENVIRONMENTAL_CONTROL_DRIFT",("humidity","temperature"),("Inspect HVAC/control loop response.","Verify sensor calibration before control intervention."))
    return tuple(sorted(out,key=lambda h:h.confidence,reverse=True)[:8])
