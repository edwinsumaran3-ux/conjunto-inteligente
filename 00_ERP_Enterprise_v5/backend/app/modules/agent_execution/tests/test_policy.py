from backend.app.modules.agent_execution.service import ToolPolicy, canonical_hash, decide

def test_disabled_tool_fails_closed():
    d=decide(policy=ToolPolicy('x','critical',True,False), requested_by='u')
    assert not d.allowed and d.status=='rejected'

def test_high_risk_requires_approval():
    d=decide(policy=ToolPolicy('x','critical',True), requested_by='u')
    assert not d.allowed and d.status=='awaiting_human'

def test_hash_is_canonical():
    assert canonical_hash({'b':2,'a':1})==canonical_hash({'a':1,'b':2})
