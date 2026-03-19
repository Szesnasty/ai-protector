"""Async LiteLLM client wrapper with multi-provider routing."""

from __future__ import annotations

import asyncio
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

_LLM_MAX_RETRIES = 2
_LLM_RETRY_BACKOFF = 1.5  # seconds; doubles each attempt

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
    intent: str = "",
) -> Any | AsyncGenerator[Any, None]:
    """Call any LLM provider via LiteLLM with automatic routing.

    Provider is detected from the model name (e.g. ``"gpt-4o"`` → OpenAI).
    For external providers the ``api_key`` parameter is required and comes
    from the ``x-api-key`` request header.  Ollama calls need no key.

    In **demo mode** (``MODE=demo``) with no API key the call is routed to
    :mod:`src.llm.mock_provider` which returns deterministic fixture
    responses based on the pipeline's ``intent`` classification.

    An API key always overrides demo mode — if the user pastes a key in
    Settings → API Keys, the real provider is used regardless of MODE.

    Args:
        messages: OpenAI-format message list.
        model: Model name (e.g. ``"gpt-4o"``, ``"claude-sonnet-4-6"``, ``"llama3.1:8b"``).
        stream: Whether to return an async streaming generator.
        temperature: Sampling temperature (0.0–2.0).
        max_tokens: Maximum tokens to generate.
        api_key: API key from browser (``x-api-key`` header). Required for external providers.
        intent: Pipeline intent classification (e.g. ``"qa"``, ``"code_gen"``). Used by MockProvider.

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

    # ── Demo mode (no API key) → MockProvider ─────────────────────
    if not api_key and settings.mode == "demo":
        from src.llm.mock_provider import mock_completion, mock_completion_stream

        logger.info("mock_provider", intent=intent, stream=stream)
        if stream:
            return mock_completion_stream(messages, intent=intent)
        return mock_completion(messages, intent=intent, stream=False)

    # ── Real provider routing ─────────────────────────────────────
    provider = detect_provider(model)
    litellm_model = format_litellm_model(model, provider)

    kwargs: dict[str, Any] = {}
    if provider == "ollama":
        kwargs["api_base"] = settings.ollama_base_url
    else:
        if not api_key:
            raise LLMError(f"API key required for provider '{provider}'. Add your key in Settings → API Keys.")
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

    last_exc: Exception | None = None
    for attempt in range(_LLM_MAX_RETRIES + 1):
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
            return response
        except AuthenticationError:
            logger.error("llm_auth_error", provider=provider)
            raise LLMError(f"Invalid API key for {provider}. Check your key in Settings → API Keys.") from None
        except ServiceUnavailableError as exc:
            last_exc = exc
            if attempt < _LLM_MAX_RETRIES:
                delay = _LLM_RETRY_BACKOFF * (2**attempt)
                logger.warning(
                    "llm_upstream_retry",
                    provider=provider,
                    attempt=attempt + 1,
                    delay=delay,
                    error=str(exc)[:120],
                )
                await asyncio.sleep(delay)
                continue
            logger.error("llm_upstream_error", error=str(exc), attempts=attempt + 1)
            raise LLMUpstreamError(f"{provider} unavailable after {attempt + 1} attempts: {exc}") from exc
        except NotFoundError as exc:
            logger.error("llm_model_not_found", model=litellm_model, error=str(exc))
            raise LLMModelNotFoundError(f"Model '{model}' not found on {provider}") from exc
        except Timeout as exc:
            logger.error("llm_timeout", model=litellm_model, error=str(exc))
            raise LLMTimeoutError(f"LLM request timed out after {settings.request_timeout}s") from exc
        except Exception as exc:
            safe_msg = str(exc)[:200] if str(exc) else "unknown"
            logger.error("llm_error", model=litellm_model, error_type=type(exc).__name__)
            raise LLMError(f"LLM error ({type(exc).__name__}): {safe_msg}") from exc

    # Should not reach here, but satisfy type checker
    raise LLMUpstreamError(f"{provider} unavailable after retries") from last_exc
