"""Dependency protocols for the Run Engine.

These define the interfaces that other modules must satisfy.
Enables testing with mocks and decouples the engine from implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from src.red_team.schemas.dataclasses import RawTargetResponse

# ---------------------------------------------------------------------------
# HTTP Client protocol
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Raw HTTP response from the target."""

    status_code: int
    body: str
    headers: dict[str, str] = field(default_factory=dict)
    latency_ms: float = 0.0


class HttpClientProtocol(Protocol):
    """Interface for sending prompts to targets."""

    async def send_prompt(self, prompt: str, target_config: dict[str, Any]) -> HttpResponse: ...


# ---------------------------------------------------------------------------
# Response Normalizer protocol
# ---------------------------------------------------------------------------


class NormalizerProtocol(Protocol):
    """Interface for normalizing raw HTTP responses."""

    def normalize(self, http_response: HttpResponse, target_config: dict[str, Any]) -> RawTargetResponse: ...


# ---------------------------------------------------------------------------
# Persistence protocol
# ---------------------------------------------------------------------------


class PersistenceProtocol(Protocol):
    """Interface for persisting run data."""

    async def create_run(self, run_data: dict[str, Any]) -> str: ...

    async def update_run(self, run_id: str, updates: dict[str, Any]) -> None: ...

    async def persist_result(self, run_id: str, result_data: dict[str, Any]) -> None: ...

    async def get_run(self, run_id: str) -> dict[str, Any] | None: ...

    async def find_active_run(self, target_fingerprint: str) -> dict[str, Any] | None: ...

    async def find_by_idempotency_key(self, key: str) -> dict[str, Any] | None: ...


# ---------------------------------------------------------------------------
# Progress Emitter protocol
# ---------------------------------------------------------------------------


class ProgressEmitterProtocol(Protocol):
    """Interface for emitting progress events."""

    async def emit(self, run_id: str, event: dict[str, Any]) -> None: ...
