from backend.app.modules.ml_lifecycle.service import evaluation_gate, drift_action

def test_metrics_boundaries():
    assert evaluation_gate({'primary_score':1,'false_positive_rate':0}).passed
    assert not evaluation_gate({'primary_score':.79,'false_positive_rate':0}).passed
    assert drift_action(0, .1) == 'observe'
