from uuid import UUID

import pytest

from backend.app.modules.digital_twin.domain.sensor_simulator import (
    PROFILES,
    generate_readings,
    get_profile,
    profile_catalog,
)
from backend.app.modules.digital_twin.domain.diagnostic_engine import diagnose_point


def test_catalog_marks_synthetic_life_safety_profiles():
    catalog = {profile["profile_id"]: profile for profile in profile_catalog()}

    assert len(catalog) == 10
    assert catalog["smoke"]["name"].endswith("(simulado)")
    assert catalog["elevator_status"]["name"].endswith("(simulado)")
    assert catalog["presence"]["supports_alarm"] is False


def test_simulation_is_repeatable_for_an_idempotency_key():
    profile = get_profile("temperature")
    run_id = UUID("43a71871-a64c-4efa-b4ed-c9c99bb4bf37")

    first = generate_readings(profile, scenario="normal", run_id=run_id)
    retry = generate_readings(profile, scenario="normal", run_id=run_id)

    assert first == retry
    assert len(first) == 5
    assert all(profile.engineering_min <= value <= profile.engineering_max for value in first)


def test_alarm_scenario_generates_a_deterministic_outlier():
    profile = get_profile("temperature")
    values = generate_readings(
        profile,
        scenario="alarm",
        run_id=UUID("43a71871-a64c-4efa-b4ed-c9c99bb4bf37"),
    )

    assert values[-1] == profile.alarm_value
    assert values[-1] > profile.engineering_max


def test_normal_and_alarm_scenarios_cross_the_existing_diagnostic_threshold_correctly():
    run_id = UUID("43a71871-a64c-4efa-b4ed-c9c99bb4bf37")
    for profile in PROFILES:
        normal = generate_readings(profile, scenario="normal", run_id=run_id)
        normal_feature = diagnose_point(
            point_id=f"normal-{profile.profile_id}", semantic_kind=profile.semantic_kind,
            values=normal, qualities=["VALID"] * len(normal),
            engineering_min=profile.engineering_min, engineering_max=profile.engineering_max,
        )
        assert normal_feature.impairment < 0.50

        if profile.supports_alarm:
            alarm = generate_readings(profile, scenario="alarm", run_id=run_id)
            alarm_quality = (
                "OUT_OF_RANGE"
                if alarm[-1] < profile.engineering_min or alarm[-1] > profile.engineering_max
                else "VALID"
            )
            alarm_feature = diagnose_point(
                point_id=f"alarm-{profile.profile_id}", semantic_kind=profile.semantic_kind,
                values=alarm, qualities=["VALID"] * (len(alarm) - 1) + [alarm_quality],
                engineering_min=profile.engineering_min, engineering_max=profile.engineering_max,
            )
            assert alarm_feature.impairment >= 0.50, profile.profile_id


def test_alarm_scenario_rejects_non_alarm_profiles():
    with pytest.raises(ValueError, match="ALARM_SCENARIO_NOT_SUPPORTED"):
        generate_readings(
            get_profile("presence"),
            scenario="alarm",
            run_id=UUID("43a71871-a64c-4efa-b4ed-c9c99bb4bf37"),
        )


def test_unknown_profiles_and_scenarios_are_rejected():
    with pytest.raises(ValueError, match="UNKNOWN_SENSOR_PROFILE"):
        get_profile("unknown")
    with pytest.raises(ValueError, match="UNKNOWN_SIMULATION_SCENARIO"):
        generate_readings(
            get_profile("temperature"),
            scenario="random",
            run_id=UUID("43a71871-a64c-4efa-b4ed-c9c99bb4bf37"),
        )
