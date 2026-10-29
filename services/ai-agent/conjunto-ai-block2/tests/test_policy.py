from decimal import Decimal
from app.policies.engine import PolicyEngine


def test_auto_approve_threshold():
    decision = PolicyEngine().evaluate(Decimal("500000"))
    assert decision.action == "auto_approve_eligible"
    assert decision.requires_human_review is False


def test_multi_quote_threshold():
    decision = PolicyEngine().evaluate(Decimal("2000000"))
    assert decision.requires_multi_quote is True
    assert decision.requires_human_review is True


def test_critical_requires_human():
    decision = PolicyEngine().evaluate(Decimal("100000"), severity="critical")
    assert decision.requires_human_review is True
