"""Deterministic engineering diagnostics for the operational digital twin.

This module deliberately does not claim machine-learning root cause analysis.
It computes auditable features from canonical telemetry: robust deviation,
trend, persistence and data-quality impairment, then ranks probable causes.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import median
from typing import Iterable

QUALITY_PENALTY = {
    "VALID": 0.0,
    "SUSPECT": 0.25,
    "STALE": 0.45,
    "OUT_OF_RANGE": 0.60,
    "BAD": 1.0,
}


@dataclass(frozen=True)
class DiagnosticFeature:
    point_id: str
    semantic_kind: str
    latest: float
    baseline: float
    scale: float
    deviation: float
    trend: float
    persistence: float
    quality_penalty: float
    impairment: float


@dataclass(frozen=True)
class DiagnosticResult:
    health_score: float
    severity: str
    confidence: float
    features: tuple[DiagnosticFeature, ...]
    probable_causes: tuple[dict, ...]


def _finite(values: Iterable[float]) -> list[float]:
    out = [float(v) for v in values if isfinite(float(v))]
    if not out:
        raise ValueError("NO_FINITE_VALUES")
    return out


def robust_scale(values: Iterable[float], engineering_span: float | None = None) -> float:
    vals = _finite(values)
    med = median(vals)
    mad = median([abs(v - med) for v in vals])
    # 6*MAD is a robust dispersion estimate; engineering span prevents
    # near-zero MAD from producing an unrealistically sensitive detector.
    candidates = [6.0 * mad]
    if engineering_span is not None and engineering_span > 0:
        candidates.append(engineering_span * 0.05)
    return max(max(candidates), 1e-9)


def trend_score(values: Iterable[float], scale: float) -> float:
    vals = _finite(values)
    if len(vals) < 2:
        return 0.0
    n = len(vals)
    xbar = (n - 1) / 2
    ybar = sum(vals) / n
    denom = sum((i - xbar) ** 2 for i in range(n))
    if denom == 0:
        return 0.0
    slope = sum((i - xbar) * (v - ybar) for i, v in enumerate(vals)) / denom
    return min(1.0, abs(slope) * (n - 1) / max(scale, 1e-9))


def classify_severity(score: float) -> str:
    if not 0 <= score <= 1:
        raise ValueError("SCORE_OUT_OF_RANGE")
    if score >= 0.90:
        return "critical"
    if score >= 0.75:
        return "high"
    if score >= 0.50:
        return "medium"
    if score >= 0.25:
        return "low"
    return "info"


def diagnose_point(
    *,
    point_id: str,
    semantic_kind: str,
    values: Iterable[float],
    qualities: Iterable[str],
    engineering_min: float | None = None,
    engineering_max: float | None = None,
) -> DiagnosticFeature:
    vals = _finite(values)
    qs = [str(q).upper() for q in qualities]
    baseline = median(vals[:-1] if len(vals) > 2 else vals)
    span = None
    if engineering_min is not None and engineering_max is not None:
        span = engineering_max - engineering_min
    scale = robust_scale(vals[:-1] if len(vals) > 2 else vals, span)
    deviation = min(1.0, abs(vals[-1] - baseline) / scale)
    trend = trend_score(vals, scale)
    persistence = sum(1 for v in vals if abs(v - baseline) > scale) / len(vals)
    quality_penalty = sum(QUALITY_PENALTY.get(q, 0.35) for q in qs) / max(len(qs), 1)
    impairment = min(1.0, 0.45 * deviation + 0.20 * trend + 0.20 * persistence + 0.15 * quality_penalty)
    return DiagnosticFeature(point_id, semantic_kind, vals[-1], baseline, scale, deviation, trend, persistence, quality_penalty, impairment)


def rank_probable_causes(features: Iterable[DiagnosticFeature]) -> tuple[dict, ...]:
    fs = list(features)
    kinds = {f.semantic_kind.lower(): f for f in fs}
    causes: list[tuple[float, dict]] = []

    def pair(a: str, b: str, code: str, description: str) -> None:
        if a in kinds and b in kinds:
            score = min(1.0, (kinds[a].impairment + kinds[b].impairment) / 1.6)
            causes.append((score, {"code": code, "description": description, "confidence": round(score, 3), "basis": [a, b]}))

    pair("temperature", "vibration", "MECHANICAL_OVERHEATING", "Concurrent thermal and vibration deviation suggests mechanical friction, bearing or alignment issues.")
    pair("pressure", "flow", "RESTRICTION_OR_BLOCKAGE", "Pressure/flow divergence is consistent with restriction, blockage or hydraulic imbalance.")
    pair("power", "temperature", "THERMAL_ELECTRICAL_STRESS", "Concurrent power and temperature deviation suggests electrical loading or cooling degradation.")
    pair("humidity", "temperature", "ENVIRONMENTAL_DRIFT", "Temperature/humidity co-movement suggests environmental-control drift.")

    for f in fs:
        if f.quality_penalty >= 0.45:
            causes.append((f.quality_penalty, {"code": "INSTRUMENTATION_QUALITY", "description": "Poor, stale or out-of-range telemetry reduces diagnostic certainty.", "confidence": round(max(0.2, 1 - f.quality_penalty), 3), "basis": [f.point_id]}))
    causes.sort(key=lambda x: x[0], reverse=True)
    return tuple(item for _, item in causes[:5])


def evaluate(features: Iterable[DiagnosticFeature]) -> DiagnosticResult:
    fs = tuple(features)
    if not fs:
        raise ValueError("NO_DIAGNOSTIC_FEATURES")
    impairment = sum(f.impairment for f in fs) / len(fs)
    quality = sum(f.quality_penalty for f in fs) / len(fs)
    health = max(0.0, min(100.0, 100.0 * (1.0 - impairment)))
    severity = classify_severity(1.0 - health / 100.0)
    confidence = max(0.0, min(1.0, 1.0 - 0.65 * quality - 0.10 / len(fs)))
    return DiagnosticResult(round(health, 3), severity, round(confidence, 3), fs, rank_probable_causes(fs))
