"""AI Protector Agent Demo — application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Proxy
    proxy_base_url: str = "http://localhost:8000/v1"

    # LLM
    default_model: str = "llama3.1:8b"
    default_model_prefix: str = "openai"
    default_policy: str = "strict"
    default_temperature: float = 0.3
    default_max_tokens: int = 1024
    litellm_log_level: str = "ERROR"

    # Agent
    max_iterations: int = 3
    max_turns: int = 20
    max_sessions: int = 100

    # App
    log_level: str = "INFO"
    app_version: str = "0.1.0"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
