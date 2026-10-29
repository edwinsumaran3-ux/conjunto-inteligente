"""Synthetic sensor profiles for exercising the digital-twin telemetry pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from random import Random
from uuid import UUID


@dataclass(frozen=True)
class SensorProfile:
    profile_id: str
    name: str
    semantic_kind: str
    unit: str
    engineering_min: float
    engineering_max: float
    normal_min: float
    normal_max: float
    alarm_value: float
    supports_alarm: bool = True


PROFILES = (
    SensorProfile("temperature", "Temperatura", "temperature", "degC", -20, 60, 23, 25, 80),
    SensorProfile("humidity", "Humedad relativa", "humidity", "%RH", 0, 100, 49, 51, 110),
    SensorProfile("water_leak", "Detección de fuga", "leak", "state", 0, 1, 0, 0, 1),
    SensorProfile("presence", "Presencia", "presence", "state", 0, 1, 0, 0, 1, False),
    SensorProfile("smoke", "Detector de humo (simulado)", "smoke", "state", 0, 1, 0, 0, 1),
    SensorProfile("power", "Consumo eléctrico", "power", "kW", 0, 500, 48, 52, 650),
    SensorProfile("pressure", "Presión de agua", "pressure", "bar", 0, 16, 3.9, 4.1, 20),
    SensorProfile("vibration", "Vibración", "vibration", "mm/s", 0, 50, 1.9, 2.1, 60),
    SensorProfile("air_quality", "Calidad del aire", "air_quality", "ppm", 300, 5000, 480, 520, 7000),
    SensorProfile("elevator_status", "Estado de ascensor (simulado)", "elevator_status", "state", 0, 1, 0, 0, 1),
)

_PROFILE_BY_ID = {profile.profile_id: profile for profile in PROFILES}


def get_profile(profile_id: str) -> SensorProfile:
    try:
        return _PROFILE_BY_ID[profile_id]
    except KeyError as exc:
        raise ValueError("UNKNOWN_SENSOR_PROFILE") from exc


def profile_catalog() -> list[dict[str, object]]:
    return [
        {
            "profile_id": profile.profile_id,
            "name": profile.name,
            "semantic_kind": profile.semantic_kind,
            "unit": profile.unit,
            "engineering_min": profile.engineering_min,
            "engineering_max": profile.engineering_max,
            "supports_alarm": profile.supports_alarm,
        }
        for profile in PROFILES
    ]


def generate_readings(
    profile: SensorProfile,
    *,
    scenario: str,
    run_id: UUID,
    count: int = 5,
) -> list[float]:
    if scenario not in {"normal", "alarm"}:
        raise ValueError("UNKNOWN_SIMULATION_SCENARIO")
    if count < 3 or count > 20:
        raise ValueError("SIMULATION_SAMPLE_COUNT_OUT_OF_RANGE")
    if scenario == "alarm" and not profile.supports_alarm:
        raise ValueError("ALARM_SCENARIO_NOT_SUPPORTED")

    random = Random(run_id.int)
    if profile.normal_min == profile.normal_max:
        values = [profile.normal_min] * count
    else:
        values = [
            round(random.uniform(profile.normal_min, profile.normal_max), 2)
            for _ in range(count)
        ]
    if scenario == "alarm":
        values[-1] = profile.alarm_value
    return values
