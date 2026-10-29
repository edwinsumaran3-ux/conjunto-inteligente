from __future__ import annotations
import hashlib, json, math, statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

@dataclass(frozen=True)
class FeaturePoint:
    name: str
    value: float
    observed_at: datetime

def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",",":"), default=str).encode()).hexdigest()

def rolling_features(points: Iterable[FeaturePoint]) -> dict[str,float]:
    xs=[float(p.value) for p in points if math.isfinite(float(p.value))]
    if not xs: raise ValueError('no_valid_observations')
    mean=statistics.fmean(xs); last=xs[-1]
    variance=statistics.pvariance(xs) if len(xs)>1 else 0.0
    return {'count':float(len(xs)),'mean':mean,'min':min(xs),'max':max(xs),'last':last,'stddev':math.sqrt(variance),'delta':last-xs[0]}

def z_score(value: float, mean: float, stddev: float) -> float:
    if not all(math.isfinite(x) for x in (value,mean,stddev)) or stddev < 0: raise ValueError('invalid_statistics')
    return 0.0 if stddev == 0 else abs(value-mean)/stddev

def governed_decision(*, proposed: str, confidence: float, min_confidence: float, allowed: set[str], model_approved: bool, route_active: bool) -> tuple[str,str]:
    if not model_approved: return 'observe','MODEL_NOT_APPROVED'
    if not route_active: return 'observe','MODEL_ROUTE_INACTIVE'
    if proposed not in allowed: return 'observe','DECISION_NOT_ALLOWED'
    if not 0 <= confidence <= 1 or confidence < min_confidence: return 'observe','CONFIDENCE_BELOW_POLICY'
    # Consequential decisions remain recommendations; execution still belongs to the existing approval plane.
    return proposed,'GOVERNED_RECOMMENDATION'
