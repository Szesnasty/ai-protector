"""AI Protector Proxy Service — application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # App
    default_policy: str = "balanced"
    log_level: str = "INFO"
    app_version: str = "0.1.0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    return Settings()
