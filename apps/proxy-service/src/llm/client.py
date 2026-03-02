"""Async LiteLLM client wrapper for Ollama."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from litellm import acompletion
from litellm.exceptions import (
    NotFoundError,
    ServiceUnavailableError,
    Timeout,
)

from src.config import get_settings
from src.llm.exceptions import LLMError, LLMModelNotFoundError, LLMTimeoutError, LLMUpstreamError

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
) -> Any | AsyncGenerator[Any, None]:
    """Call Ollama via LiteLLM.

    Args:
        messages: OpenAI-format message list.
        model: Model name without provider prefix (e.g. "llama3.1:8b").
        stream: Whether to return an async streaming generator.
        temperature: Sampling temperature (0.0–2.0).
        max_tokens: Maximum tokens to generate.

    Returns:
        Full response dict (non-streaming) or async generator (streaming).

    Raises:
        LLMUpstreamError: Provider is unreachable.
        LLMModelNotFoundError: Model does not exist.
        LLMTimeoutError: Request timed out.
        LLMError: Any other LLM error.
    """
    settings = get_settings()

    if temperature is None:
        temperature = settings.default_temperature

    litellm_model = f"ollama/{model}"

    logger.debug(
        "llm_request",
        model=litellm_model,
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
            api_base=settings.ollama_base_url,
            timeout=settings.request_timeout,
        )
    except ServiceUnavailableError as exc:
        logger.error("llm_upstream_error", error=str(exc))
        raise LLMUpstreamError(f"Ollama unavailable: {exc}") from exc
    except NotFoundError as exc:
        logger.error("llm_model_not_found", model=litellm_model, error=str(exc))
        raise LLMModelNotFoundError(f"Model '{model}' not found") from exc
    except Timeout as exc:
        logger.error("llm_timeout", model=litellm_model, error=str(exc))
        raise LLMTimeoutError(f"LLM request timed out after {settings.request_timeout}s") from exc
    except Exception as exc:
        logger.error("llm_error", model=litellm_model, error=str(exc), error_type=type(exc).__name__)
        raise LLMError(f"LLM error: {exc}") from exc

    return response
