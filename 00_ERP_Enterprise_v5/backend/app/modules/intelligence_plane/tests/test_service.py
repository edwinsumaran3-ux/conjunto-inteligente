from datetime import datetime, timezone, timedelta
import pytest
from backend.app.modules.intelligence_plane.service import FeaturePoint, rolling_features, z_score, governed_decision

def test_rolling_features_and_delta():
    base=datetime(2026,1,1,tzinfo=timezone.utc)
    f=rolling_features([FeaturePoint('temp',10,base),FeaturePoint('temp',12,base+timedelta(minutes=1)),FeaturePoint('temp',14,base+timedelta(minutes=2))])
    assert f['mean']==12 and f['last']==14 and f['delta']==4

def test_zero_stddev_is_not_nan():
    assert z_score(5,5,0)==0

def test_governance_fails_closed():
    assert governed_decision(proposed='shutdown',confidence=.99,min_confidence=.8,allowed={'observe'},model_approved=True,route_active=True)==('observe','DECISION_NOT_ALLOWED')
    assert governed_decision(proposed='alert',confidence=.95,min_confidence=.8,allowed={'alert'},model_approved=False,route_active=True)==('observe','MODEL_NOT_APPROVED')
    assert governed_decision(proposed='alert',confidence=.95,min_confidence=.8,allowed={'alert'},model_approved=True,route_active=True)==('alert','GOVERNED_RECOMMENDATION')
