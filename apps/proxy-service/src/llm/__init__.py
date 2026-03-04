"""LLM client package."""

from src.llm.client import llm_completion
from src.llm.exceptions import LLMError, LLMModelNotFoundError, LLMTimeoutError, LLMUpstreamError
from src.llm.providers import EXTERNAL_MODELS, detect_provider, format_litellm_model

__all__ = [
    "EXTERNAL_MODELS",
    "LLMError",
    "LLMModelNotFoundError",
    "LLMTimeoutError",
    "LLMUpstreamError",
    "detect_provider",
    "format_litellm_model",
    "llm_completion",
]
