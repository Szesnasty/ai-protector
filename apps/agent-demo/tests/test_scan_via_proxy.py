"""Tests for _scan_via_proxy — URL construction and error handling.

These tests verify the actual HTTP call layer that was previously untested.
Every other test mocks _scan_via_proxy entirely, which let a double-/v1/
URL bug ship to production undetected.
"""

from __future__ import annotations

import pytest

from src.agent.nodes.llm_call import _scan_via_proxy
from src.config import get_settings

# ── Helpers ──────────────────────────────────────────────────

_BASE_KWARGS = {
    "session_id": "test-session",
    "policy": "balanced",
    "api_key": None,
    "scan_messages": [{"role": "user", "content": "hello"}],
    "model_name": "llama3.1:8b",
    "temperature": 0.3,
    "max_tokens": 1024,
}


def _allow_response() -> dict:
    return {
        "decision": "ALLOW",
        "risk_score": 0.1,
        "risk_flags": {},
        "intent": "qa",
        "blocked_reason": None,
        "scanner_results": None,
        "node_timings": {},
    }


def _block_response() -> dict:
    return {
        "decision": "BLOCK",
        "risk_score": 0.9,
        "risk_flags": {"suspicious_intent": 0.8},
        "intent": "jailbreak",
        "blocked_reason": "Jailbreak attempt detected.",
        "scanner_results": None,
        "node_timings": {},
    }


# ── URL construction ────────────────────────────────────────


class TestScanURLConstruction:
    """Verify scan URL is built correctly from proxy_base_url."""

    @pytest.mark.asyncio
    async def test_url_no_double_v1(self, httpx_mock):
        """proxy_base_url ending with /v1 must NOT produce /v1/v1/scan."""
        httpx_mock.add_response(
            url="http://localhost:8000/v1/scan",
            json=_allow_response(),
            status_code=200,
        )

        result = await _scan_via_proxy(
            proxy_base_url="http://localhost:8000/v1",
            **_BASE_KWARGS,
        )

        assert result["decision"] == "ALLOW"
        assert result["status_code"] == 200
        # Verify the request went to the correct URL
        request = httpx_mock.get_request()
        assert request is not None
        assert str(request.url) == "http://localhost:8000/v1/scan"

    @pytest.mark.asyncio
    async def test_url_matches_settings_default(self, httpx_mock):
        """URL must match what get_settings().proxy_base_url + /scan produces."""
        settings = get_settings()
        expected_url = f"{settings.proxy_base_url}/scan"

        httpx_mock.add_response(
            url=expected_url,
            json=_allow_response(),
            status_code=200,
        )

        result = await _scan_via_proxy(
            proxy_base_url=settings.proxy_base_url,
            **_BASE_KWARGS,
        )

        assert result["status_code"] == 200
        request = httpx_mock.get_request()
        assert str(request.url) == expected_url

    @pytest.mark.asyncio
    async def test_url_docker_compose_base(self, httpx_mock):
        """Docker Compose uses http://proxy-service:8000/v1 — must work."""
        httpx_mock.add_response(
            url="http://proxy-service:8000/v1/scan",
            json=_allow_response(),
            status_code=200,
        )

        result = await _scan_via_proxy(
            proxy_base_url="http://proxy-service:8000/v1",
            **_BASE_KWARGS,
        )

        request = httpx_mock.get_request()
        assert str(request.url) == "http://proxy-service:8000/v1/scan"
        assert result["decision"] == "ALLOW"


# ── Response handling ────────────────────────────────────────


class TestScanResponseHandling:
    """Verify correct handling of proxy responses — especially error cases."""

    @pytest.mark.asyncio
    async def test_allow_response(self, httpx_mock):
        httpx_mock.add_response(json=_allow_response(), status_code=200)

        result = await _scan_via_proxy(
            proxy_base_url="http://localhost:8000/v1",
            **_BASE_KWARGS,
        )

        assert result["status_code"] == 200
        assert result["decision"] == "ALLOW"

    @pytest.mark.asyncio
    async def test_block_response(self, httpx_mock):
        httpx_mock.add_response(json=_block_response(), status_code=403)

        result = await _scan_via_proxy(
            proxy_base_url="http://localhost:8000/v1",
            **_BASE_KWARGS,
        )

        assert result["status_code"] == 403
        assert result["decision"] == "BLOCK"
        assert result["intent"] == "jailbreak"

    @pytest.mark.asyncio
    async def test_404_raises_runtime_error(self, httpx_mock):
        """404 (wrong URL) must NOT silently default to ALLOW."""
        httpx_mock.add_response(
            json={"detail": "Not Found"},
            status_code=404,
        )

        with pytest.raises(RuntimeError, match="Unexpected proxy response 404"):
            await _scan_via_proxy(
                proxy_base_url="http://localhost:8000/v1",
                **_BASE_KWARGS,
            )

    @pytest.mark.asyncio
    async def test_500_raises_runtime_error(self, httpx_mock):
        """500 from proxy must NOT silently default to ALLOW."""
        httpx_mock.add_response(
            json={"detail": "Internal Server Error"},
            status_code=500,
        )

        with pytest.raises(RuntimeError, match="Unexpected proxy response 500"):
            await _scan_via_proxy(
                proxy_base_url="http://localhost:8000/v1",
                **_BASE_KWARGS,
            )

    @pytest.mark.asyncio
    async def test_422_raises_runtime_error(self, httpx_mock):
        """422 (invalid request body) must NOT silently default to ALLOW."""
        httpx_mock.add_response(
            json={"detail": "Validation error"},
            status_code=422,
        )

        with pytest.raises(RuntimeError, match="Unexpected proxy response 422"):
            await _scan_via_proxy(
                proxy_base_url="http://localhost:8000/v1",
                **_BASE_KWARGS,
            )


# ── Headers ──────────────────────────────────────────────────


class TestScanRequestHeaders:
    """Verify correct request headers are sent to proxy."""

    @pytest.mark.asyncio
    async def test_headers_without_api_key(self, httpx_mock):
        httpx_mock.add_response(json=_allow_response(), status_code=200)

        await _scan_via_proxy(
            proxy_base_url="http://localhost:8000/v1",
            session_id="sess-123",
            policy="strict",
            api_key=None,
            scan_messages=[{"role": "user", "content": "hi"}],
            model_name="llama3.1:8b",
            temperature=0.3,
            max_tokens=1024,
        )

        req = httpx_mock.get_request()
        assert req.headers["x-client-id"] == "agent-sess-123"
        assert req.headers["x-policy"] == "strict"
        assert req.headers["x-correlation-id"] == "sess-123"
        assert "x-api-key" not in req.headers

    @pytest.mark.asyncio
    async def test_headers_with_api_key(self, httpx_mock):
        httpx_mock.add_response(json=_allow_response(), status_code=200)

        await _scan_via_proxy(
            proxy_base_url="http://localhost:8000/v1",
            session_id="sess-456",
            policy="balanced",
            api_key="sk-test-key-abc",
            scan_messages=[{"role": "user", "content": "hi"}],
            model_name="gemini-2.0-flash",
            temperature=0.5,
            max_tokens=2048,
        )

        req = httpx_mock.get_request()
        assert req.headers["x-api-key"] == "sk-test-key-abc"
        assert req.headers["x-policy"] == "balanced"

    @pytest.mark.asyncio
    async def test_request_body_structure(self, httpx_mock):
        httpx_mock.add_response(json=_allow_response(), status_code=200)

        messages = [
            {"role": "user", "content": "What is 2+2?"},
        ]

        await _scan_via_proxy(
            proxy_base_url="http://localhost:8000/v1",
            session_id="sess-body",
            policy="balanced",
            api_key=None,
            scan_messages=messages,
            model_name="gpt-4o",
            temperature=0.7,
            max_tokens=512,
        )

        import json

        req = httpx_mock.get_request()
        body = json.loads(req.content)
        assert body["model"] == "gpt-4o"
        assert body["messages"] == messages
        assert body["temperature"] == 0.7
        assert body["max_tokens"] == 512
        assert body["stream"] is False
