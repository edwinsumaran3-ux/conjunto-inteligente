from __future__ import annotations
import hashlib
import time
from dataclasses import dataclass
from typing import Any
from app.providers.base import LLMProvider
from app.providers.http import ProviderError


@dataclass
class Circuit:
    failures: int = 0
    opened_until: float = 0.0


class LLMOrchestrator:
    def __init__(
        self,
        providers: list[LLMProvider],
        *,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
        max_input_chars: int = 30000,
        max_output_chars: int = 12000,
    ) -> None:
        if not providers:
            raise ValueError("At least one provider is required")
        self.providers, self.failure_threshold, self.cooldown_seconds = (
            providers,
            failure_threshold,
            cooldown_seconds,
        )
        self.max_input_chars, self.max_output_chars = max_input_chars, max_output_chars
        self.circuits = {p.name: Circuit() for p in providers}
        self.cache: dict[str, tuple[float, dict[str, Any]]] = {}

    def _key(self, system: str, user: str, context: dict[str, Any] | None) -> str:
        raw = system + "\n" + user + "\n" + repr(sorted((context or {}).items()))
        return hashlib.sha256(raw.encode()).hexdigest()

    def _allowed(self, name: str) -> bool:
        return time.monotonic() >= self.circuits[name].opened_until

    def _success(self, name: str) -> None:
        self.circuits[name] = Circuit()

    def _failure(self, name: str) -> None:
        c = self.circuits[name]
        c.failures += 1
        if c.failures >= self.failure_threshold:
            c.opened_until = time.monotonic() + self.cooldown_seconds

    async def generate(
        self, *, system: str, user: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if len(system) + len(user) > self.max_input_chars:
            raise ValueError("LLM input exceeds configured limit")
        key = self._key(system, user, context)
        cached = self.cache.get(key)
        if cached and cached[0] > time.monotonic():
            return {**cached[1], "cache_hit": True}
        errors: list[str] = []
        for provider in self.providers:
            if not self._allowed(provider.name):
                errors.append(f"{provider.name}: circuit_open")
                continue
            try:
                result = await provider.generate(
                    system=system, user=user, context=context
                )
                text = result.get("text") if isinstance(result, dict) else None
                if (
                    not isinstance(text, str)
                    or not text.strip()
                    or len(text) > self.max_output_chars
                ):
                    raise ProviderError("invalid provider output")
                self._success(provider.name)
                result = {**result, "cache_hit": False, "fallback": bool(errors)}
                self.cache[key] = (time.monotonic() + 15.0, result)
                return result
            except Exception as exc:
                self._failure(provider.name)
                errors.append(f"{provider.name}: {type(exc).__name__}")
        raise ProviderError(
            "All configured LLM providers unavailable: " + ", ".join(errors)
        )
