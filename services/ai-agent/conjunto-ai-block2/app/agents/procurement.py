from app.providers.base import LLMProvider
from app.policies.engine import PolicyEngine
from app.schemas.procurement import ProcurementRequest
from app.schemas.common import AIResponse


class ProcurementAgent:
    name = "procurement"

    def __init__(self, policy: PolicyEngine, provider: LLMProvider):
        self.policy = policy
        self.provider = provider

    async def run(self, request: ProcurementRequest) -> AIResponse:
        decision = self.policy.evaluate(
            request.amount_cop, request.urgency, request.severity
        )
        generated = await self.provider.generate(
            system="Prepare a procurement recommendation. Never execute a purchase.",
            user=request.description,
            context={
                "policy": decision.__dict__,
                "amount_cop": str(request.amount_cop),
            },
        )
        return AIResponse(
            request_id=request.request_id,
            status="completed",
            agent=self.name,
            confidence=0.0,
            requires_human_review=decision.requires_human_review,
            data_source_status="not_required",
            result={
                "policy": decision.__dict__,
                "recommendation": generated["text"],
                "provider": generated.get("provider"),
                "fallback": generated.get("fallback", False),
            },
            warnings=["The AI service does not authorize or execute purchases."],
        )
