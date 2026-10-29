"""Pure governance rules for the machine-learning lifecycle."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class GateResult:
    passed: bool
    reason: str

def evaluation_gate(metrics: dict, *, min_score: float = 0.80, max_false_positive_rate: float = 0.10) -> GateResult:
    score = metrics.get("primary_score")
    fpr = metrics.get("false_positive_rate")
    if not isinstance(score, (int, float)) or not isinstance(fpr, (int, float)):
        return GateResult(False, "required evaluation metrics are missing")
    if not 0 <= score <= 1 or not 0 <= fpr <= 1:
        return GateResult(False, "evaluation metrics must be normalized to [0,1]")
    if score < min_score:
        return GateResult(False, "primary score is below promotion threshold")
    if fpr > max_false_positive_rate:
        return GateResult(False, "false-positive rate is above safety threshold")
    return GateResult(True, "evaluation gate passed")

def drift_action(value: float, threshold: float) -> str:
    if threshold < 0 or value < 0:
        raise ValueError("drift values must be non-negative")
    if value > threshold * 2:
        return "rollback"
    if value >= threshold:
        return "pause"
    return "observe"

def deployment_allowed(*, model_approved: bool, evaluation_passed: bool, artifact_verified: bool) -> bool:
    return bool(model_approved and evaluation_passed and artifact_verified)
