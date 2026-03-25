"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class Settings:
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    app_mode: Literal["raw", "protected"] = "raw"

    ai_protector_base_url: str = ""
    ai_protector_api_key: str = ""

    enable_streaming: bool = True
    enable_retrieval: bool = True
    enable_tools: bool = False
    enable_structured_output: bool = True
    enable_canary: bool = True

    static_auth_token: str = ""
    port: int = 8010

    model_timeout: int = 30

    # Storage limits
    max_conversations: int = 200
    max_traces: int = 1000
    max_messages_per_conversation: int = 50


def _bool_env(key: str, default: bool) -> bool:
    val = os.environ.get(key, "").lower()
    if val in ("true", "1", "yes"):
        return True
    if val in ("false", "0", "no"):
        return False
    return default


def load_settings() -> Settings:
    return Settings(
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        app_mode="protected"
        if os.environ.get("APP_MODE", "raw").lower() == "protected"
        else "raw",
        ai_protector_base_url=os.environ.get("AI_PROTECTOR_BASE_URL", ""),
        ai_protector_api_key=os.environ.get("AI_PROTECTOR_API_KEY", ""),
        enable_streaming=_bool_env("ENABLE_STREAMING", True),
        enable_retrieval=_bool_env("ENABLE_RETRIEVAL", True),
        enable_tools=_bool_env("ENABLE_TOOLS", False),
        enable_structured_output=_bool_env("ENABLE_STRUCTURED_OUTPUT", True),
        enable_canary=_bool_env("ENABLE_CANARY", True),
        static_auth_token=os.environ.get("STATIC_AUTH_TOKEN", ""),
        port=int(os.environ.get("PORT", "8010")),
        model_timeout=int(os.environ.get("MODEL_TIMEOUT", "30")),
    )
