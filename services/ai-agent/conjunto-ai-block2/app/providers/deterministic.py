from typing import Any
from .base import LLMProvider


class DeterministicProvider(LLMProvider):
    name = "deterministic"

    async def generate(
        self, *, system: str, user: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return {
            "text": "Deterministic provider response. LLM generation is disabled for this environment.",
            "system": system,
            "input": user,
            "context": context or {},
        }
