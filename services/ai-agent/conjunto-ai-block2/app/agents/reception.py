from app.schemas.reception import ReceptionRequest
from app.schemas.common import AIResponse
from app.tools.registry import ToolRegistry
from app.providers.base import LLMProvider


class ReceptionAgent:
    name = "reception"

    def __init__(self, tools: ToolRegistry, provider: LLMProvider):
        self.tools = tools
        self.provider = provider

    async def run(self, request: ReceptionRequest) -> AIResponse:
        keywords = [word for word in request.message.lower().split() if len(word) >= 4][
            :8
        ]
        area = await self.tools.execute(
            "get_area_by_keywords", keywords=keywords or [request.message]
        )
        generated = await self.provider.generate(
            system="Classify and route reception requests using only supplied evidence.",
            user=request.message,
            context={"area": area},
        )
        return AIResponse(
            request_id=request.request_id,
            status="completed",
            agent=self.name,
            confidence=0.0,
            requires_human_review=False,
            data_source_status="available",
            result={
                "area": area,
                "response": generated["text"],
                "provider": generated.get("provider"),
                "fallback": generated.get("fallback", False),
            },
        )
