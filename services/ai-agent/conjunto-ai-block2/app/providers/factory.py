from app.core.config import get_settings
from .base import LLMProvider
from .deterministic import DeterministicProvider
from .http import (
    OpenAIResponsesProvider,
    AnthropicMessagesProvider,
    OllamaProvider,
    GeminiProvider,
    OpenAICompatibleProvider,
)
from .resilient import ResilientProvider


def build_providers() -> list[LLMProvider]:
    s = get_settings()
    requested = [p.strip().lower() for p in s.llm_provider.split(",") if p.strip()]
    allowed = {
        p.strip().lower() for p in s.llm_allowed_providers.split(",") if p.strip()
    }
    providers: list[LLMProvider] = []
    for name in requested:
        if name not in allowed:
            continue
        if name == "deterministic":
            providers.append(DeterministicProvider())
        elif name == "openai" and s.openai_api_key:
            providers.append(
                OpenAIResponsesProvider(
                    api_key=s.openai_api_key,
                    model=s.openai_model,
                    timeout=s.llm_timeout_seconds,
                )
            )
        elif name == "anthropic" and s.anthropic_api_key:
            providers.append(
                AnthropicMessagesProvider(
                    api_key=s.anthropic_api_key,
                    model=s.anthropic_model,
                    timeout=s.llm_timeout_seconds,
                )
            )
        elif name == "gemini" and s.gemini_api_key:
            providers.append(
                GeminiProvider(
                    api_key=s.gemini_api_key,
                    model=s.gemini_model,
                    timeout=s.llm_timeout_seconds,
                )
            )
        elif name == "ollama":
            providers.append(
                OllamaProvider(
                    base_url=s.ollama_base_url,
                    model=s.ollama_model,
                    timeout=s.llm_timeout_seconds,
                )
            )
        elif name == "openai_compatible" and s.compat_base_url:
            providers.append(
                OpenAICompatibleProvider(
                    api_key=s.compat_api_key or "",
                    model=s.compat_model,
                    base_url=s.compat_base_url,
                    timeout=s.llm_timeout_seconds,
                )
            )
    if not providers:
        raise ValueError("No usable LLM provider configured or allowed")
    return providers


def build_provider() -> LLMProvider:
    return ResilientProvider(build_providers())


def get_provider() -> LLMProvider:
    return build_provider()
