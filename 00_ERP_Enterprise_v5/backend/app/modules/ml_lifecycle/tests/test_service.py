from backend.app.modules.ml_lifecycle.service import evaluation_gate, drift_action, deployment_allowed

def test_evaluation_gate_fail_closed():
    assert not evaluation_gate({}).passed
    assert evaluation_gate({'primary_score': .91, 'false_positive_rate': .04}).passed

def test_drift_escalation():
    assert drift_action(.2, .1) == 'pause'
    assert drift_action(.21, .1) == 'rollback'
    assert drift_action(.01, .1) == 'observe'

def test_promotion_requires_all_gates():
    assert deployment_allowed(model_approved=True, evaluation_passed=True, artifact_verified=True)
    assert not deployment_allowed(model_approved=True, evaluation_passed=True, artifact_verified=False)
