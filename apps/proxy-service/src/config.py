"""AI Protector Proxy Service — application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_package_version() -> str:
    """Read version from installed package metadata (pyproject.toml)."""
    try:
        from importlib.metadata import version

        return version("ai-protector-proxy")
    except Exception:
        return "0.0.0-unknown"


class Settings(BaseSettings):
    """Central configuration loaded from environment / .env file."""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_protector"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Ollama / LLM
    ollama_base_url: str = "http://localhost:11434"
    default_model: str = "llama3.1:8b"

    # Langfuse
    langfuse_host: str = "http://localhost:3001"
    langfuse_public_key: str = "pk-lf-local"
    langfuse_secret_key: str = "sk-lf-local"

    # LLM defaults
    default_temperature: float = 0.7
    default_max_tokens: int = 4096
    litellm_log_level: str = "ERROR"
    request_timeout: int = 120  # seconds — max wait for LLM response

    # App
    mode: str = "demo"  # "demo" | "real" — demo uses MockProvider when no API key
    default_policy: str = "balanced"
    log_level: str = "INFO"
    json_logs: bool = False  # True for production (structured JSON to stdout)
    app_version: str = _get_package_version()

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://frontend:3000",
    ]

    # Security scanners
    enable_llm_guard: bool = True
    enable_nemo_guardrails: bool = True
    scanner_timeout: int = 30  # Max seconds per scanner

    # Presidio PII
    enable_presidio: bool = True
    presidio_language: str = "en"
    presidio_score_threshold: float = 0.4
    presidio_spacy_model: str = "en_core_web_sm"  # en_core_web_lg for prod

    # Compare demo
    enable_direct_endpoint: bool = True  # Set False in production

    # Langfuse tracing
    enable_langfuse: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    return Settings()
