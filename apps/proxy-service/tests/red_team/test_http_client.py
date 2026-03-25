"""Tests for the HTTP Client module (08-http-client)."""

from __future__ import annotations

import json

import httpx
import pytest

from src.red_team.engine.http_client.client import HttpResponse, TargetEndpoint, send_prompt

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _target(url: str = "http://test-target/v1/chat", **kwargs) -> TargetEndpoint:
    return TargetEndpoint(url=url, **kwargs)


def _mock_client(
    status: int = 200,
    body: str | dict = '{"reply":"ok"}',
    headers: dict[str, str] | None = None,
) -> httpx.AsyncClient:
    """Return an AsyncClient backed by a MockTransport."""
    resp_headers = headers or {}

    if isinstance(body, dict):
        body = json.dumps(body)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=body, headers=resp_headers)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# Basic request/response
# ---------------------------------------------------------------------------


class TestSendPromptSuccess:
    async def test_returns_http_response(self) -> None:
        client = _mock_client(200, '{"reply":"hello"}')
        result = await send_prompt("hi", _target(), client=client)

        assert isinstance(result, HttpResponse)
        assert result.status_code == 200
        assert result.body == '{"reply":"hello"}'

    async def test_body_is_raw_text(self) -> None:
        """HTTP Client must NOT parse JSON — returns raw text."""
        raw = '{"tool_calls": [{"name": "search"}]}'
        client = _mock_client(200, raw)
        result = await send_prompt("test", _target(), client=client)
        assert result.body == raw
        # Verify it's a string, not a parsed dict
        assert isinstance(result.body, str)

    async def test_latency_measured(self) -> None:
        client = _mock_client(200)
        result = await send_prompt("test", _target(), client=client)
        assert result.latency_ms >= 0.0

    async def test_no_tool_call_extraction(self) -> None:
        """HTTP Client does NOT extract tool calls — that's the normalizer's job."""
        body = json.dumps({"tool_calls": [{"name": "exec", "args": {"cmd": "rm -rf /"}}]})
        client = _mock_client(200, body)
        result = await send_prompt("test", _target(), client=client)
        # The response is raw text, no special processing
        assert "tool_calls" in result.body
        assert not hasattr(result, "tool_calls")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestAuthHeader:
    async def test_auth_header_included(self) -> None:
        captured_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, text="{}")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        await send_prompt(
            "hi",
            _target(auth_header="Bearer secret-token"),
            client=client,
        )
        assert captured_headers.get("authorization") == "Bearer secret-token"

    async def test_no_auth_header_when_none(self) -> None:
        captured_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, text="{}")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        await send_prompt("hi", _target(auth_header=None), client=client)
        assert "authorization" not in captured_headers


# ---------------------------------------------------------------------------
# Request format
# ---------------------------------------------------------------------------


class TestRequestFormat:
    async def test_sends_json_with_messages_field(self) -> None:
        captured_body: list[bytes] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_body.append(request.content)
            return httpx.Response(200, text="{}")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        await send_prompt("attack prompt", _target(), client=client)

        payload = json.loads(captured_body[0])
        assert payload == {"messages": [{"role": "user", "content": "attack prompt"}]}

    async def test_content_type_header(self) -> None:
        captured_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, text="{}")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        await send_prompt("x", _target(content_type="application/json"), client=client)
        assert captured_headers.get("content-type") == "application/json"


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------


class TestResponseHeaders:
    async def test_headers_lowercase(self) -> None:
        """Response header keys must be lowercased."""
        client = _mock_client(200, "{}", headers={"X-Custom-Header": "val"})
        result = await send_prompt("x", _target(), client=client)
        # httpx already lowercases headers, but our code also enforces it
        assert "x-custom-header" in result.headers
        assert result.headers["x-custom-header"] == "val"


# ---------------------------------------------------------------------------
# Non-2xx
# ---------------------------------------------------------------------------


class TestNon2xx:
    async def test_400_still_returns_response(self) -> None:
        client = _mock_client(400, '{"error":"bad request"}')
        result = await send_prompt("x", _target(), client=client)
        assert result.status_code == 400
        assert "bad request" in result.body

    async def test_500_still_returns_response(self) -> None:
        client = _mock_client(500, "Internal Server Error")
        result = await send_prompt("x", _target(), client=client)
        assert result.status_code == 500

    async def test_403_still_returns_response(self) -> None:
        client = _mock_client(403, '{"error":"forbidden"}')
        result = await send_prompt("x", _target(), client=client)
        assert result.status_code == 403


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    async def test_timeout_raises_timeout_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with pytest.raises(TimeoutError, match="did not respond within"):
            await send_prompt("x", _target(timeout_s=1), client=client)

    async def test_connection_error_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with pytest.raises(ConnectionError, match="Cannot reach target"):
            await send_prompt("x", _target(), client=client)

    async def test_network_error_raises_connection_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.NetworkError("network down")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        with pytest.raises(ConnectionError, match="Cannot reach target"):
            await send_prompt("x", _target(), client=client)


# ---------------------------------------------------------------------------
# Data type tests
# ---------------------------------------------------------------------------


class TestDataTypes:
    def test_target_endpoint_defaults(self) -> None:
        t = TargetEndpoint(url="http://x")
        assert t.timeout_s == 30
        assert t.content_type == "application/json"
        assert t.auth_header is None

    def test_http_response_frozen(self) -> None:
        r = HttpResponse(status_code=200, body="ok", latency_ms=1.0)
        with pytest.raises(AttributeError):
            r.status_code = 500  # type: ignore[misc]

    def test_target_endpoint_frozen(self) -> None:
        t = TargetEndpoint(url="http://x")
        with pytest.raises(AttributeError):
            t.url = "http://y"  # type: ignore[misc]
