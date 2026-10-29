from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def generate(
        self, *, system: str, user: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        raise NotImplementedError
