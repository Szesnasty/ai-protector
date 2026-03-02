"""Tests for the health endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def client():
    """Async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """GET /health should return 200 with status field."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert "services" in data
    assert "version" in data
    assert set(data["services"].keys()) == {"db", "redis", "ollama", "langfuse"}


@pytest.mark.asyncio
async def test_health_has_correlation_id(client: AsyncClient):
    """Health response should include X-Correlation-ID header."""
    response = await client.get("/health")
    assert "x-correlation-id" in response.headers
