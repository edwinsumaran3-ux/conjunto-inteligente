from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = Field("conjunto-ai", validation_alias="AI__SERVICE_NAME")
    environment: str = Field("development", validation_alias="AI__ENV")
    llm_provider: str = Field("deterministic", validation_alias="AI__LLM_PROVIDER")
    llm_allowed_providers: str = Field(
        "deterministic", validation_alias="AI__LLM_ALLOWED_PROVIDERS"
    )
    openai_model: str = Field("gpt-5-mini", validation_alias="OPENAI_MODEL")
    anthropic_model: str = Field(
        "claude-sonnet-4-5", validation_alias="ANTHROPIC_MODEL"
    )
    gemini_model: str = Field("gemini-3.8-flash", validation_alias="GEMINI_MODEL")
    ollama_model: str = Field("llama3.2:3b", validation_alias="OLLAMA_MODEL")
    ollama_base_url: str = Field(
        "http://ollama:11434", validation_alias="AI__OLLAMA_BASE_URL"
    )
    compat_base_url: str = Field("", validation_alias="AI__COMPAT_BASE_URL")
    compat_model: str = Field("local-model", validation_alias="AI__COMPAT_MODEL")
    llm_timeout_seconds: float = Field(20.0, validation_alias="AI__LLM_TIMEOUT_SECONDS")
    llm_failure_threshold: int = Field(3, validation_alias="AI__LLM_FAILURE_THRESHOLD")
    llm_cooldown_seconds: float = Field(
        30.0, validation_alias="AI__LLM_COOLDOWN_SECONDS"
    )
    llm_max_input_chars: int = Field(30000, validation_alias="AI__LLM_MAX_INPUT_CHARS")
    llm_max_output_chars: int = Field(
        12000, validation_alias="AI__LLM_MAX_OUTPUT_CHARS"
    )
    core_base_url: str = Field("http://api:5000", validation_alias="CORE__BASE_URL")
    core_timeout_seconds: float = Field(5.0, validation_alias="CORE__TIMEOUT_SECONDS")
    core_max_retries: int = Field(3, validation_alias="CORE__MAX_RETRIES")
    auto_approve_limit_cop: int = Field(
        500000, validation_alias="AI__AUTO_APPROVE_LIMIT_COP"
    )
    multi_quote_limit_cop: int = Field(
        2000000, validation_alias="AI__MULTI_QUOTE_LIMIT_COP"
    )
    openai_api_key: str | None = Field(None, validation_alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(None, validation_alias="ANTHROPIC_API_KEY")
    gemini_api_key: str | None = Field(None, validation_alias="GEMINI_API_KEY")
    compat_api_key: str | None = Field(None, validation_alias="AI__COMPAT_API_KEY")
    internal_service_token: str | None = Field(
        None, validation_alias="AI__INTERNAL_SERVICE_TOKEN"
    )
    otel_endpoint: str = Field(
        "http://otel-collector:4317", validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_service_name: str = Field("conjunto-ai", validation_alias="OTEL_SERVICE_NAME")
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
