from __future__ import annotations
from typing import Any
from app.core.config import get_settings
from app.core.orchestrator import LLMOrchestrator
from .base import LLMProvider


class ResilientProvider(LLMProvider):
    name = "resilient"

    def __init__(self, providers: list[LLMProvider]) -> None:
        s = get_settings()
        self.orchestrator = LLMOrchestrator(
            providers,
            failure_threshold=s.llm_failure_threshold,
            cooldown_seconds=s.llm_cooldown_seconds,
            max_input_chars=s.llm_max_input_chars,
            max_output_chars=s.llm_max_output_chars,
        )

    async def generate(
        self, *, system: str, user: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self.orchestrator.generate(
            system=system, user=user, context=context
        )
