from backend.app.modules.digital_twin.domain.advanced_diagnostics import normalized_change_point, lagged_alignment, build_hypotheses


def test_change_point_detects_step_change():
    cp = normalized_change_point([10,10,10,10,20,20,20,20], 1.0)
    assert cp.detected and cp.direction == 'up' and cp.magnitude == 1.0


def test_lagged_alignment_finds_one_sample_shift():
    r = lagged_alignment([1,3,2,5,4,6], [0,1,3,2,5,4], max_lag=2)
    assert r['lag_samples'] == 1
    assert r['absolute_correlation'] > .99


def test_hypothesis_is_probable_not_certain():
    hs = build_hypotheses([
        {'point_id':'t','semantic_kind':'temperature','impairment':.8,'quality_penalty':0},
        {'point_id':'v','semantic_kind':'vibration','impairment':.7,'quality_penalty':0},
    ])
    assert hs and hs[0].code == 'MECHANICAL_DEGRADATION'
    assert hs[0].confidence < 1.0
