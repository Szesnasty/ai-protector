"""Async LiteLLM client wrapper with multi-provider routing."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from litellm import acompletion
from litellm.exceptions import (
    AuthenticationError,
    NotFoundError,
    ServiceUnavailableError,
    Timeout,
)

from src.config import get_settings
from src.llm.exceptions import LLMError, LLMModelNotFoundError, LLMTimeoutError, LLMUpstreamError
from src.llm.providers import detect_provider, format_litellm_model

logger = structlog.get_logger()

# Silence verbose LiteLLM logs at module load
_settings = get_settings()
os.environ.setdefault("LITELLM_LOG", _settings.litellm_log_level)


async def llm_completion(
    messages: list[dict[str, Any]],
    model: str,
    stream: bool = False,
    temperature: float | None = None,
    max_tokens: int | None = None,
    api_key: str | None = None,
) -> Any | AsyncGenerator[Any, None]:
    """Call any LLM provider via LiteLLM with automatic routing.

    Provider is detected from the model name (e.g. ``"gpt-4o"`` → OpenAI).
    For external providers the ``api_key`` parameter is required and comes
    from the ``x-api-key`` request header.  Ollama calls need no key.

    Args:
        messages: OpenAI-format message list.
        model: Model name (e.g. ``"gpt-4o"``, ``"claude-3.5-sonnet"``, ``"llama3.1:8b"``).
        stream: Whether to return an async streaming generator.
        temperature: Sampling temperature (0.0–2.0).
        max_tokens: Maximum tokens to generate.
        api_key: API key from browser (``x-api-key`` header). Required for external providers.

    Returns:
        Full response dict (non-streaming) or async generator (streaming).

    Raises:
        LLMError: Missing API key for external provider (401).
        LLMUpstreamError: Provider is unreachable.
        LLMModelNotFoundError: Model does not exist.
        LLMTimeoutError: Request timed out.
    """
    settings = get_settings()

    if temperature is None:
        temperature = settings.default_temperature

    provider = detect_provider(model)
    litellm_model = format_litellm_model(model, provider)

    kwargs: dict[str, Any] = {}
    if provider == "ollama":
        kwargs["api_base"] = settings.ollama_base_url
    else:
        if not api_key:
            raise LLMError(
                f"API key required for provider '{provider}'. "
                f"Add your key in Settings → API Keys."
            )
        kwargs["api_key"] = api_key

    logger.debug(
        "llm_request",
        model=litellm_model,
        provider=provider,
        stream=stream,
        temperature=temperature,
        max_tokens=max_tokens,
        message_count=len(messages),
    )

    try:
        response = await acompletion(
            model=litellm_model,
            messages=messages,
            stream=stream,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=settings.request_timeout,
            **kwargs,
        )
    except AuthenticationError as exc:
        logger.error("llm_auth_error", provider=provider, error=str(exc))
        raise LLMError(f"Invalid API key for {provider}: {exc}") from exc
    except ServiceUnavailableError as exc:
        logger.error("llm_upstream_error", error=str(exc))
        raise LLMUpstreamError(f"{provider} unavailable: {exc}") from exc
    except NotFoundError as exc:
        logger.error("llm_model_not_found", model=litellm_model, error=str(exc))
        raise LLMModelNotFoundError(f"Model '{model}' not found on {provider}") from exc
    except Timeout as exc:
        logger.error("llm_timeout", model=litellm_model, error=str(exc))
        raise LLMTimeoutError(f"LLM request timed out after {settings.request_timeout}s") from exc
    except Exception as exc:
        logger.error("llm_error", model=litellm_model, error=str(exc), error_type=type(exc).__name__)
        raise LLMError(f"LLM error: {exc}") from exc

    return response
