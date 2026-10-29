from uuid import uuid4
from app.governance.contracts import AgentName, MemoryRecord
from app.governance.registry import CONTRACTS
from app.governance.service import AgentGovernance


def test_all_agent_contracts_are_declared():
    assert set(CONTRACTS) == set(AgentName)


def test_memory_requires_tenant_source_confidence_and_version():
    record = MemoryRecord(
        tenant_id="t1",
        agent=AgentName.SECURITY,
        source="sensor:event",
        content={"x": 1},
        confidence=0.91,
        version=1,
    )
    assert record.tenant_id == "t1"
    assert record.confidence == 0.91


def test_consequential_actions_require_human():
    execution = AgentGovernance().start(
        request_id=uuid4(),
        trace_id=None,
        tenant_id="t1",
        agent="finance",
        action="pay",
        payload={"amount": 100},
    )
    assert execution.requires_human_review is True
