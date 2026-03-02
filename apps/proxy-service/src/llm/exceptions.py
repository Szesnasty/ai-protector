"""Custom exception classes for LLM operations."""


class LLMError(Exception):
    """Base exception for LLM-related errors."""

    status_code: int = 500
    error_type: str = "llm_error"

    def __init__(self, message: str = "Internal LLM error") -> None:
        self.message = message
        super().__init__(self.message)


class LLMUpstreamError(LLMError):
    """LLM provider is unreachable or returned a server error."""

    status_code: int = 502
    error_type: str = "upstream_error"

    def __init__(self, message: str = "LLM provider unavailable") -> None:
        super().__init__(message)


class LLMModelNotFoundError(LLMError):
    """Requested model does not exist on the provider."""

    status_code: int = 404
    error_type: str = "model_not_found"

    def __init__(self, message: str = "Model not found") -> None:
        super().__init__(message)


class LLMTimeoutError(LLMError):
    """Request to LLM provider timed out."""

    status_code: int = 504
    error_type: str = "timeout"

    def __init__(self, message: str = "LLM request timed out") -> None:
        super().__init__(message)
