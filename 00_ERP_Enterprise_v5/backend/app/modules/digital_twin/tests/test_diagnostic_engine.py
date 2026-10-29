from backend.app.modules.digital_twin.domain.diagnostic_engine import diagnose_point, evaluate, classify_severity


def test_robust_diagnostic_detects_persistent_deviation():
    f = diagnose_point(point_id='p1', semantic_kind='temperature', values=[20, 20, 20, 32], qualities=['VALID']*4)
    r = evaluate([f])
    assert f.deviation > 0.9
    assert r.health_score < 70
    assert r.severity in {'medium', 'high', 'critical'}


def test_quality_reduces_confidence_without_fabricating_cause():
    f = diagnose_point(point_id='p1', semantic_kind='temperature', values=[20, 20, 20], qualities=['BAD']*3)
    r = evaluate([f])
    assert r.confidence < 0.5
    assert any(c['code'] == 'INSTRUMENTATION_QUALITY' for c in r.probable_causes)


def test_severity_boundaries_are_deterministic():
    assert classify_severity(0.24) == 'info'
    assert classify_severity(0.50) == 'medium'
    assert classify_severity(0.90) == 'critical'
