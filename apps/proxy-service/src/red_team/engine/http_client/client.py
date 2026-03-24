"""HTTP Client — sends attack prompts to target endpoints.

This is the only module in red-team that makes network calls.
It returns a raw ``HttpResponse``; the Response Normalizer converts
that into the canonical ``RawTargetResponse`` for evaluators.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TargetEndpoint:
    """Configuration for the target endpoint to probe."""

    url: str
    auth_header: str | None = None  # Decrypted at call time, never stored/logged
    timeout_s: int = 30
    content_type: str = "application/json"


@dataclass(frozen=True)
class HttpResponse:
    """Raw HTTP response from the target — no parsing, no tool extraction."""

    status_code: int
    headers: dict[str, str] = field(default_factory=dict)  # lowercase keys
    body: str = ""  # raw text
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# send_prompt
# ---------------------------------------------------------------------------


async def send_prompt(
    prompt: str,
    target: TargetEndpoint,
    *,
    client: httpx.AsyncClient | None = None,
) -> HttpResponse:
    """Send *prompt* as a POST to *target* and return the raw response.

    Parameters
    ----------
    prompt:
        The attack / test prompt string.
    target:
        Target endpoint configuration.
    client:
        Optional pre-configured ``httpx.AsyncClient``.  When ``None`` a
        short-lived client is created for the single request.

    Raises
    ------
    TimeoutError
        When the target does not respond within ``target.timeout_s``.
    ConnectionError
        When the target is unreachable or an SSL error occurs.
    """
    headers: dict[str, str] = {"Content-Type": target.content_type}
    if target.auth_header:
        headers["Authorization"] = target.auth_header

    payload = {"message": prompt}

    async def _do(c: httpx.AsyncClient) -> HttpResponse:
        start = time.monotonic()
        try:
            resp = await c.post(
                target.url,
                json=payload,
                headers=headers,
                timeout=target.timeout_s,
            )
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Target did not respond within {target.timeout_s}s") from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise ConnectionError(f"Cannot reach target at {target.url}: {exc}") from exc

        elapsed_ms = (time.monotonic() - start) * 1000

        # Lowercase all header keys for consistent downstream access.
        resp_headers = {k.lower(): v for k, v in resp.headers.items()}

        return HttpResponse(
            status_code=resp.status_code,
            headers=resp_headers,
            body=resp.text,
            latency_ms=elapsed_ms,
        )

    if client is not None:
        return await _do(client)

    async with httpx.AsyncClient() as auto_client:
        return await _do(auto_client)
