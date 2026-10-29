from backend.app.modules.digital_twin.domain.system_diagnostics import aggregate_health, propagate_impact

def test_aggregate_health_is_weighted_and_confidence_aware():
    result=aggregate_health({'a':80,'b':40},{'a':2,'b':1},{'a':1,'b':.5})
    assert result.health_score == 66.667
    assert result.severity == 'medium'
    assert result.confidence == .833

def test_propagation_respects_criticality_and_factor():
    paths=propagate_impact('A',[
        {'source':'A','target':'B','relation':'feeds','criticality':1,'propagation_factor':.8},
        {'source':'B','target':'C','relation':'depends_on','criticality':.75,'propagation_factor':.8},
        {'source':'A','target':'D','relation':'weak','criticality':.2,'propagation_factor':.2},
    ])
    assert [(p.target,p.depth) for p in paths] == [('B',1),('C',2)]
    assert paths[1].impact == .48
