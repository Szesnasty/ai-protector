"""Provider detection and routing for LiteLLM."""

from __future__ import annotations

# Pattern → Provider mapping (order matters: first match wins)
PROVIDER_RULES: list[tuple[str, str]] = [
    # Explicit prefixes (user-provided)
    ("ollama/", "ollama"),
    ("anthropic/", "anthropic"),
    ("gemini/", "google"),
    ("mistral/", "mistral"),
    ("azure/", "azure"),
    # Model name patterns (no prefix needed)
    ("gpt-", "openai"),
    ("o1", "openai"),
    ("o3", "openai"),
    ("claude-", "anthropic"),
    ("gemini-", "google"),
    ("mistral-", "mistral"),
    ("codestral", "mistral"),
]

# Static catalog of well-known external models
EXTERNAL_MODELS: list[dict[str, str]] = [
    {"id": "gpt-4o", "provider": "openai", "name": "GPT-4o"},
    {"id": "gpt-4o-mini", "provider": "openai", "name": "GPT-4o Mini"},
    {"id": "gpt-4-turbo", "provider": "openai", "name": "GPT-4 Turbo"},
    {"id": "o1", "provider": "openai", "name": "o1"},
    {"id": "o3-mini", "provider": "openai", "name": "o3-mini"},
    {"id": "claude-sonnet-4-6", "provider": "anthropic", "name": "Claude Sonnet 4.6"},
    {"id": "claude-haiku-4-5", "provider": "anthropic", "name": "Claude Haiku 4.5"},
    {"id": "claude-opus-4-6", "provider": "anthropic", "name": "Claude Opus 4.6"},
    {"id": "gemini-2.5-flash", "provider": "google", "name": "Gemini 2.5 Flash"},
    {"id": "gemini-2.0-flash", "provider": "google", "name": "Gemini 2.0 Flash"},
    {"id": "gemini-pro", "provider": "google", "name": "Gemini Pro"},
    {"id": "mistral-large", "provider": "mistral", "name": "Mistral Large"},
    {"id": "mistral-medium", "provider": "mistral", "name": "Mistral Medium"},
    {"id": "codestral", "provider": "mistral", "name": "Codestral"},
]


def detect_provider(model: str) -> str:
    """Detect LLM provider from model name.

    Returns ``"ollama"`` as default for unrecognized models (backward compatible).
    """
    model_lower = model.lower()
    for pattern, provider in PROVIDER_RULES:
        if model_lower.startswith(pattern):
            return provider
    return "ollama"


def format_litellm_model(model: str, provider: str) -> str:
    """Format model name for LiteLLM.

    LiteLLM expects certain prefixes:
    - OpenAI: ``"gpt-4o"`` (as-is, no prefix)
    - Anthropic: ``"anthropic/claude-sonnet-4-6"`` (needs prefix if not present)
    - Google: ``"gemini/gemini-2.5-flash"`` (as-is if prefixed)
    - Ollama: ``"ollama/llama3.1:8b"`` (needs prefix if not present)
    """
    if provider == "ollama" and not model.startswith("ollama/"):
        return f"ollama/{model}"
    if provider == "anthropic" and not model.startswith("anthropic/"):
        return f"anthropic/{model}"
    if provider == "google" and not model.startswith("gemini/"):
        return f"gemini/{model}"
    if provider == "mistral" and not model.startswith("mistral/"):
        return f"mistral/{model}"
    # OpenAI: no prefix needed
    return model
