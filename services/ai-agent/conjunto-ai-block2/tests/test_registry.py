from app.governance.registry import get_contract, authorize_tool


def test_each_agent_has_bounded_contract():
    from app.governance.contracts import AgentName

    for name in AgentName:
        c = get_contract(name.value)
        assert c.mission and c.max_tool_calls > 0 and c.max_context_items > 0


def test_agent_cannot_use_another_agents_write_tool():
    assert authorize_tool("surveillance_advisor", "dispatch_drone", True)
    assert not authorize_tool("reporting", "dispatch_drone", True)
