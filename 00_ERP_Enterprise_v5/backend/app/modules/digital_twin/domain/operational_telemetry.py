"""Engineering-grade telemetry normalization and quality classification.

Pure domain logic: no database, network, or implicit unit conversion.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

QUALITY_VALID = "VALID"
QUALITY_SUSPECT = "SUSPECT"
QUALITY_BAD = "BAD"
QUALITY_OUT_OF_RANGE = "OUT_OF_RANGE"
QUALITY_STALE = "STALE"
QUALITY_DUPLICATE = "DUPLICATE"


@dataclass(frozen=True)
class NormalizedMeasurement:
    raw_value: float
    raw_unit: str | None
    canonical_value: float
    canonical_unit: str | None


def _norm(unit: str | None) -> str | None:
    return unit.strip().lower() if unit else None


def normalize_measurement(value: float, unit: str | None, canonical_unit: str | None) -> NormalizedMeasurement:
    """Convert only explicitly supported engineering units; reject ambiguous conversions."""
    src, dst = _norm(unit), _norm(canonical_unit)
    if dst is None or src == dst:
        return NormalizedMeasurement(value, unit, value, canonical_unit or unit)
    conversions = {
        ("c", "k"): lambda x: x + 273.15,
        ("k", "c"): lambda x: x - 273.15,
        ("c", "f"): lambda x: x * 9 / 5 + 32,
        ("f", "c"): lambda x: (x - 32) * 5 / 9,
        ("kpa", "pa"): lambda x: x * 1000,
        ("pa", "kpa"): lambda x: x / 1000,
        ("bar", "pa"): lambda x: x * 100000,
        ("pa", "bar"): lambda x: x / 100000,
        ("kw", "w"): lambda x: x * 1000,
        ("w", "kw"): lambda x: x / 1000,
        ("l/s", "m3/s"): lambda x: x / 1000,
        ("m3/s", "l/s"): lambda x: x * 1000,
    }
    converter = conversions.get((src, dst))
    if converter is None:
        raise ValueError(f"UNSUPPORTED_UNIT_CONVERSION:{unit}->{canonical_unit}")
    return NormalizedMeasurement(value, unit, converter(value), canonical_unit)


def classify_quality(
    *,
    observed_at: datetime,
    received_at: datetime,
    source_quality: str,
    value: float,
    engineering_min: float | None,
    engineering_max: float | None,
    stale_after_seconds: int,
    future_tolerance_seconds: int = 30,
) -> tuple[str, str]:
    """Return deterministic quality code and reason; source BAD always remains BAD."""
    source = source_quality.upper()
    if source in {"BAD", "INVALID", "ERROR"}:
        return QUALITY_BAD, "SOURCE_REPORTED_BAD"
    if observed_at > received_at + timedelta(seconds=future_tolerance_seconds):
        return QUALITY_SUSPECT, "OBSERVATION_TIME_IN_FUTURE"
    age = (received_at - observed_at).total_seconds()
    if age > stale_after_seconds:
        return QUALITY_STALE, "OBSERVATION_OLDER_THAN_STALE_THRESHOLD"
    if engineering_min is not None and value < engineering_min:
        return QUALITY_OUT_OF_RANGE, "BELOW_ENGINEERING_LIMIT"
    if engineering_max is not None and value > engineering_max:
        return QUALITY_OUT_OF_RANGE, "ABOVE_ENGINEERING_LIMIT"
    if source not in {"GOOD", "VALID", "OK"}:
        return QUALITY_SUSPECT, "SOURCE_QUALITY_NOT_CONFIRMED"
    return QUALITY_VALID, "WITHIN_ENGINEERING_LIMITS"
