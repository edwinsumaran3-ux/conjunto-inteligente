from datetime import datetime, timezone, timedelta
import pytest
from backend.app.modules.digital_twin.domain.operational_telemetry import normalize_measurement, classify_quality

def test_temperature_normalization_is_explicit():
    m=normalize_measurement(0,'C','K')
    assert round(m.canonical_value,2)==273.15

def test_unsupported_conversion_is_rejected():
    with pytest.raises(ValueError): normalize_measurement(10,'psi','C')

def test_bad_source_never_becomes_valid():
    now=datetime.now(timezone.utc)
    q,_=classify_quality(observed_at=now,received_at=now,source_quality='BAD',value=1,engineering_min=None,engineering_max=None,stale_after_seconds=300)
    assert q=='BAD'

def test_out_of_range_is_deterministic():
    now=datetime.now(timezone.utc)
    q,r=classify_quality(observed_at=now,received_at=now,source_quality='GOOD',value=110,engineering_min=0,engineering_max=100,stale_after_seconds=300)
    assert (q,r)==('OUT_OF_RANGE','ABOVE_ENGINEERING_LIMIT')

def test_stale_is_not_silently_valid():
    now=datetime.now(timezone.utc)
    q,r=classify_quality(observed_at=now-timedelta(seconds=301),received_at=now,source_quality='GOOD',value=1,engineering_min=None,engineering_max=None,stale_after_seconds=300)
    assert q=='STALE'
