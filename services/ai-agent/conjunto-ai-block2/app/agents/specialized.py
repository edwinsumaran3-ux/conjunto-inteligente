from dataclasses import dataclass
from uuid import UUID

from app.providers.base import LLMProvider
from app.schemas.common import AIResponse

AGENT_NAMES = [
    "plan",
    "maintenance",
    "vendor",
    "inventory",
    "finance",
    "security",
    "communication",
    "reporting",
    "compliance",
    "surveillance_advisor",
]


@dataclass(frozen=True)
class SpecializedRequest:
    request_id: UUID
    message: str
    tenant_id: str


class SpecializedAgent:
    def __init__(self, name: str, provider: LLMProvider) -> None:
        if name not in AGENT_NAMES:
            raise ValueError(f"Unsupported agent: {name}")
        self.name = name
        self.provider = provider

    async def run(self, request: SpecializedRequest) -> AIResponse:
        generated = await self.provider.generate(
            system=f"You are the {self.name} agent. Use only supplied evidence. Never execute critical actions. Escalate uncertain or consequential decisions to a human.",
            user=request.message,
            context={"tenant_id": request.tenant_id, "agent": self.name},
        )
        return AIResponse(
            request_id=request.request_id,
            status="completed",
            agent=self.name,
            confidence=0.0,
            requires_human_review=True,
            data_source_status="available",
            result={
                "response": generated["text"],
                "provider": generated.get("provider"),
                "fallback": generated.get("fallback", False),
                "action": "human_review_required",
            },
        )
