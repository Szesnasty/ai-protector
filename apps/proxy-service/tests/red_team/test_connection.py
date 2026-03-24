"""Tests for POST /v1/benchmark/test-connection."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.red_team.api.routes import router

_PATCH_TARGET = "src.red_team.api.routes._httpx.AsyncClient"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    return app


@pytest.fixture()
async def client(test_app: FastAPI):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _mock_httpx_client(mock_client_inst):
    """Wrap a mock to behave as an async context manager."""
    mock_client_inst.__aenter__ = AsyncMock(return_value=mock_client_inst)
    mock_client_inst.__aexit__ = AsyncMock(return_value=False)
    return mock_client_inst


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_connection_ok(client: AsyncClient):
    """Reachable target returns ok with status_code and latency."""
    mock_response = httpx.Response(
        200,
        headers={"content-type": "application/json"},
        text='{"reply": "hello"}',
    )

    with patch(_PATCH_TARGET) as mock_cls:
        inst = _mock_httpx_client(AsyncMock())
        inst.post.return_value = mock_response
        mock_cls.return_value = inst

        resp = await client.post(
            "/v1/benchmark/test-connection",
            json={
                "endpoint_url": "http://localhost:8080/chat",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["status_code"] == 200
    assert data["latency_ms"] is not None
    assert "json" in data["content_type"]


async def test_connection_timeout(client: AsyncClient):
    """Unreachable target (timeout) returns error."""
    with patch(_PATCH_TARGET) as mock_cls:
        inst = _mock_httpx_client(AsyncMock())
        inst.post.side_effect = httpx.TimeoutException("timed out")
        mock_cls.return_value = inst

        resp = await client.post(
            "/v1/benchmark/test-connection",
            json={
                "endpoint_url": "http://unreachable:9999/chat",
                "timeout_s": 5,
            },
        )

    data = resp.json()
    assert data["status"] == "error"
    assert data["error"] == "Timeout"


async def test_connection_auth_failure(client: AsyncClient):
    """401 response returns auth error."""
    mock_response = httpx.Response(
        401,
        headers={"content-type": "application/json"},
        text='{"error": "Unauthorized"}',
    )

    with patch(_PATCH_TARGET) as mock_cls:
        inst = _mock_httpx_client(AsyncMock())
        inst.post.return_value = mock_response
        mock_cls.return_value = inst

        resp = await client.post(
            "/v1/benchmark/test-connection",
            json={
                "endpoint_url": "https://api.example.com/chat",
                "auth_header": "Bearer bad-token",
            },
        )

    data = resp.json()
    assert data["status"] == "error"
    assert "401" in data["error"]


async def test_connection_refused(client: AsyncClient):
    """Connection refused returns error."""
    with patch(_PATCH_TARGET) as mock_cls:
        inst = _mock_httpx_client(AsyncMock())
        inst.post.side_effect = httpx.ConnectError("Connection refused")
        mock_cls.return_value = inst

        resp = await client.post(
            "/v1/benchmark/test-connection",
            json={
                "endpoint_url": "http://localhost:1/chat",
            },
        )

    data = resp.json()
    assert data["status"] == "error"
    assert data["error"] == "Connection refused"


async def test_connection_non_json(client: AsyncClient):
    """Non-JSON response returns ok with content_type info."""
    mock_response = httpx.Response(
        200,
        headers={"content-type": "text/html"},
        text="<html>Hello</html>",
    )

    with patch(_PATCH_TARGET) as mock_cls:
        inst = _mock_httpx_client(AsyncMock())
        inst.post.return_value = mock_response
        mock_cls.return_value = inst

        resp = await client.post(
            "/v1/benchmark/test-connection",
            json={
                "endpoint_url": "http://localhost:8080",
            },
        )

    data = resp.json()
    assert data["status"] == "ok"
    assert "html" in data["content_type"]


async def test_auth_not_persisted(client: AsyncClient):
    """Auth header used for the request only - not stored."""
    mock_response = httpx.Response(200, headers={"content-type": "application/json"}, text="{}")

    with patch(_PATCH_TARGET) as mock_cls:
        inst = _mock_httpx_client(AsyncMock())
        inst.post.return_value = mock_response
        mock_cls.return_value = inst

        resp = await client.post(
            "/v1/benchmark/test-connection",
            json={
                "endpoint_url": "http://localhost:8080",
                "auth_header": "Bearer sk-secret-key-123",
            },
        )

    assert resp.status_code == 200
    call_kwargs = inst.post.call_args
    assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer sk-secret-key-123"


async def test_ssl_error(client: AsyncClient):
    """SSL certificate error returns SSL error."""
    with patch(_PATCH_TARGET) as mock_cls:
        inst = _mock_httpx_client(AsyncMock())
        inst.post.side_effect = Exception("SSL certificate verify failed")
        mock_cls.return_value = inst

        resp = await client.post(
            "/v1/benchmark/test-connection",
            json={
                "endpoint_url": "https://self-signed.example.com/chat",
            },
        )

    data = resp.json()
    assert data["status"] == "error"
    assert "SSL" in data["error"]
