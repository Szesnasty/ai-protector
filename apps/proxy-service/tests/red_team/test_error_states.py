"""Tests for P2-08 Error States — structured error responses.

Covers: error format, test-connection error codes, 404/409 responses.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.red_team.api import StructuredError, StructuredErrorResponse
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
    mock_client_inst.__aenter__ = AsyncMock(return_value=mock_client_inst)
    mock_client_inst.__aexit__ = AsyncMock(return_value=False)
    return mock_client_inst


# ---------------------------------------------------------------------------
# Structured error model tests
# ---------------------------------------------------------------------------


def test_structured_error_model():
    """StructuredErrorResponse has correct shape."""
    err = StructuredErrorResponse(
        error=StructuredError(
            code="connection_failed",
            message="Cannot reach target",
            details={"url": "http://example.com"},
        )
    )
    d = err.model_dump()
    assert d["error"]["code"] == "connection_failed"
    assert d["error"]["message"] == "Cannot reach target"
    assert d["error"]["details"]["url"] == "http://example.com"


def test_structured_error_minimal():
    """StructuredError works without details."""
    err = StructuredError(code="not_found", message="Run not found")
    assert err.details is None


# ---------------------------------------------------------------------------
# Test-connection error codes
# ---------------------------------------------------------------------------


async def test_connection_timeout_error_code(client: AsyncClient):
    """Timeout returns error_code='timeout'."""
    with patch(_PATCH_TARGET) as mock_cls:
        inst = _mock_httpx_client(AsyncMock())
        inst.post.side_effect = httpx.TimeoutException("timed out")
        mock_cls.return_value = inst

        resp = await client.post(
            "/v1/benchmark/test-connection",
            json={"endpoint_url": "http://unreachable:9999/chat"},
        )

    data = resp.json()
    assert data["error_code"] == "timeout"
    assert data["error"] == "Timeout"


async def test_connection_refused_error_code(client: AsyncClient):
    """Connection refused returns error_code='connection_failed'."""
    with patch(_PATCH_TARGET) as mock_cls:
        inst = _mock_httpx_client(AsyncMock())
        inst.post.side_effect = httpx.ConnectError("Connection refused")
        mock_cls.return_value = inst

        resp = await client.post(
            "/v1/benchmark/test-connection",
            json={"endpoint_url": "http://localhost:1/chat"},
        )

    data = resp.json()
    assert data["error_code"] == "connection_failed"


async def test_auth_invalid_error_code(client: AsyncClient):
    """401 returns error_code='auth_invalid'."""
    mock_resp = httpx.Response(401, headers={"content-type": "application/json"}, text="{}")

    with patch(_PATCH_TARGET) as mock_cls:
        inst = _mock_httpx_client(AsyncMock())
        inst.post.return_value = mock_resp
        mock_cls.return_value = inst

        resp = await client.post(
            "/v1/benchmark/test-connection",
            json={"endpoint_url": "https://api.example.com", "auth_header": "Bearer bad"},
        )

    data = resp.json()
    assert data["error_code"] == "auth_invalid"
    assert "401" in data["error"]


async def test_ssl_error_code(client: AsyncClient):
    """SSL error returns error_code='ssl_error'."""
    with patch(_PATCH_TARGET) as mock_cls:
        inst = _mock_httpx_client(AsyncMock())
        inst.post.side_effect = Exception("SSL certificate verify failed")
        mock_cls.return_value = inst

        resp = await client.post(
            "/v1/benchmark/test-connection",
            json={"endpoint_url": "https://self-signed.example.com"},
        )

    data = resp.json()
    assert data["error_code"] == "ssl_error"


async def test_ok_no_error_code(client: AsyncClient):
    """Successful connection has error_code=None."""
    mock_resp = httpx.Response(200, headers={"content-type": "application/json"}, text="{}")

    with patch(_PATCH_TARGET) as mock_cls:
        inst = _mock_httpx_client(AsyncMock())
        inst.post.return_value = mock_resp
        mock_cls.return_value = inst

        resp = await client.post(
            "/v1/benchmark/test-connection",
            json={"endpoint_url": "http://localhost:8080"},
        )

    data = resp.json()
    assert data["status"] == "ok"
    assert data["error_code"] is None


# ---------------------------------------------------------------------------
# 404 for non-existent run
# ---------------------------------------------------------------------------


async def test_run_not_found_404(client: AsyncClient):
    """GET /runs/:id returns 404 for unknown run."""
    with patch("src.red_team.api.service.BenchmarkService.get_run_safe", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        resp = await client.get("/v1/benchmark/runs/00000000-0000-0000-0000-000000000001")
    assert resp.status_code == 404
    data = resp.json()
    assert "detail" in data


# ---------------------------------------------------------------------------
# Non-JSON response is OK (not blocking)
# ---------------------------------------------------------------------------


async def test_non_json_response_is_ok(client: AsyncClient):
    """Non-JSON 200 response returns status=ok (warning level, not error)."""
    mock_resp = httpx.Response(200, headers={"content-type": "text/html"}, text="<html>Hi</html>")

    with patch(_PATCH_TARGET) as mock_cls:
        inst = _mock_httpx_client(AsyncMock())
        inst.post.return_value = mock_resp
        mock_cls.return_value = inst

        resp = await client.post(
            "/v1/benchmark/test-connection",
            json={"endpoint_url": "http://localhost:8080"},
        )

    data = resp.json()
    assert data["status"] == "ok"
    assert "html" in data["content_type"]
    # Not an error — just informational
    assert data["error_code"] is None
