import pytest
from app.core.orchestrator import LLMOrchestrator
from app.core.response_guard import ResponseGuard
from app.core.tool_policy import ToolPolicy
from app.providers.base import LLMProvider
from app.providers.http import ProviderError


class Good(LLMProvider):
    name = "good"

    async def generate(self, **kwargs):
        return {"text": "safe answer", "provider": self.name}


class Bad(LLMProvider):
    name = "bad"

    async def generate(self, **kwargs):
        raise ProviderError("down")


@pytest.mark.asyncio
async def test_failover_and_cache():
    o = LLMOrchestrator([Bad(), Good()], failure_threshold=1, cooldown_seconds=60)
    r = await o.generate(system="s", user="u")
    assert r["provider"] == "good" and r["fallback"] is True
    r2 = await o.generate(system="s", user="u")
    assert r2["cache_hit"] is True


@pytest.mark.asyncio
async def test_circuit_opens():
    o = LLMOrchestrator([Bad(), Good()], failure_threshold=1, cooldown_seconds=60)
    await o.generate(system="s", user="u")
    assert o.circuits["bad"].opened_until > 0


def test_response_guard():
    g = ResponseGuard()
    ok, w = g.validate({"text": "Approve_purchase now"})
    assert ok and "critical_action_language_detected" in w
    assert "[REDACTED]" in g.sanitize("api_key=SECRET")


def test_tool_policy():
    p = ToolPolicy()
    assert p.decide(tool="get_asset_history").allowed
    assert not p.decide(tool="approve_purchase").allowed
    assert p.decide(tool="approve_purchase", actor="human", approved=True).allowed
    assert not p.decide(tool="unknown").allowed


@pytest.mark.asyncio
async def test_input_limit_is_enforced():
    o = LLMOrchestrator([Good()], max_input_chars=3)
    with pytest.raises(ValueError):
        await o.generate(system="long", user="input")


def test_unknown_tool_is_denied():
    decision = ToolPolicy().decide(tool="format_database")
    assert decision.allowed is False
