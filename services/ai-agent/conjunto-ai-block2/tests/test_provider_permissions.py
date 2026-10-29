from app.providers.factory import build_providers
from app.core.config import get_settings


def test_provider_allowlist_filters_requested_provider(monkeypatch):
    monkeypatch.setenv("AI__LLM_PROVIDER", "deterministic,ollama")
    monkeypatch.setenv("AI__LLM_ALLOWED_PROVIDERS", "deterministic")
    get_settings.cache_clear()
    providers = build_providers()
    assert [p.name for p in providers] == ["deterministic"]
    get_settings.cache_clear()


def test_ollama_is_allowed_without_api_key(monkeypatch):
    monkeypatch.setenv("AI__LLM_PROVIDER", "ollama,deterministic")
    monkeypatch.setenv("AI__LLM_ALLOWED_PROVIDERS", "ollama,deterministic")
    monkeypatch.setenv("AI__OLLAMA_BASE_URL", "http://ollama:11434")
    get_settings.cache_clear()
    providers = build_providers()
    assert [p.name for p in providers] == ["ollama", "deterministic"]
    get_settings.cache_clear()
