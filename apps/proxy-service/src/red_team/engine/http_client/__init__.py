"""HTTP Client — sends attack prompts to target endpoints."""

from src.red_team.engine.http_client.client import (
    HttpResponse,
    TargetEndpoint,
    send_prompt,
)

__all__ = [
    "HttpResponse",
    "TargetEndpoint",
    "send_prompt",
]
