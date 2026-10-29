from app.integrations.core_client import CoreUnavailableError
from app.schemas.diagnostic import DiagnosticRequest
from app.schemas.common import AIResponse
from app.tools.registry import ToolRegistry
from app.providers.base import LLMProvider


class DiagnosticAgent:
    name = "diagnostic"

    def __init__(self, tools: ToolRegistry, provider: LLMProvider):
        self.tools = tools
        self.provider = provider

    async def run(self, request: DiagnosticRequest) -> AIResponse:
        try:
            history = await self.tools.execute(
                "get_asset_history", asset_id=request.asset_id
            )
        except CoreUnavailableError:
            return AIResponse(
                request_id=request.request_id,
                status="degraded",
                agent=self.name,
                confidence=0.0,
                requires_human_review=True,
                data_source_status="unavailable",
                result={},
                warnings=[
                    "Core service unavailable; no conclusion was generated from missing data."
                ],
            )
        generated = await self.provider.generate(
            system="Analyze observations using supplied asset evidence. Do not invent missing evidence.",
            user=request.observation,
            context={"asset_history": history},
        )
        return AIResponse(
            request_id=request.request_id,
            status="completed",
            agent=self.name,
            confidence=0.0,
            requires_human_review=True,
            data_source_status="available",
            result={
                "asset_id": request.asset_id,
                "analysis": generated["text"],
                "provider": generated.get("provider"),
                "fallback": generated.get("fallback", False),
                "evidence": history,
            },
            warnings=["AI output does not replace qualified technical inspection."],
        )
