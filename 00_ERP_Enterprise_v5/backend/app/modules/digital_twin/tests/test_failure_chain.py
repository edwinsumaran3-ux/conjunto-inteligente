from datetime import datetime, timezone, timedelta
from backend.app.modules.digital_twin.domain.failure_chain import build_failure_chain


def test_dependency_temporal_chain_is_ranked_not_proven():
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    events = [
        {'anomaly_id':'a1','node_id':'pump','detected_at':t,'score':.8},
        {'anomaly_id':'a2','node_id':'loop','detected_at':t+timedelta(minutes=5),'score':.7},
        {'anomaly_id':'a3','node_id':'building','detected_at':t+timedelta(minutes=10),'score':.6},
    ]
    relations = [
        {'source':'pump','target':'loop','criticality':.9,'propagation_factor':.8},
        {'source':'loop','target':'building','criticality':.8,'propagation_factor':.9},
    ]
    result = build_failure_chain(events, relations, 1800)
    assert result.ordered_anomalies == ('a1','a2','a3')
    assert len(result.links) == 2
    assert all(x.relation == 'dependency_propagation_candidate' for x in result.links)
    assert result.claim_level == 'correlation_with_dependency_evidence'
    assert all('root_cause_not_proven' in x.evidence for x in result.links)


def test_large_gap_does_not_create_link():
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    events = [
        {'anomaly_id':'a1','node_id':'n1','detected_at':t},
        {'anomaly_id':'a2','node_id':'n2','detected_at':t+timedelta(hours=3)},
    ]
    result = build_failure_chain(events, [], 3600)
    assert result.links == ()


def test_temporal_only_link_is_explicitly_non_causal():
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    events = [
        {'anomaly_id':'a1','node_id':'n1','detected_at':t},
        {'anomaly_id':'a2','node_id':'n2','detected_at':t+timedelta(minutes=1)},
    ]
    result = build_failure_chain(events, [], 600)
    assert len(result.links) == 1
    assert result.links[0].relation == 'temporal_precursor_candidate'
    assert result.links[0].dependency_factor == 0.0
