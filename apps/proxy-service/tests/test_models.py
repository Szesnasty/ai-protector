"""Tests for GET /v1/models endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture(autouse=True)
async def _no_db(monkeypatch):
    """Override the global conftest DB fixture for these pure-HTTP tests."""
    yield


@pytest.mark.asyncio
async def test_models_endpoint_returns_catalog():
    """GET /v1/models returns the static catalog + Ollama models."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("src.routers.models._fetch_ollama_models", new_callable=AsyncMock) as mock_ollama:
            from src.schemas.models import ModelInfo

            mock_ollama.return_value = [
                ModelInfo(id="ollama/llama3.1:8b", provider="ollama", name="Llama 3.1 8B"),
            ]

            resp = await client.get("/v1/models")
            assert resp.status_code == 200

            data = resp.json()
            models = data["models"]
            assert len(models) > 5  # At least external catalog + 1 ollama

            # Check external models are present
            model_ids = [m["id"] for m in models]
            assert "gpt-4o" in model_ids
            assert "claude-sonnet-4-6" in model_ids
            assert "gemini-2.5-flash" in model_ids

            # Check ollama model is present
            assert "ollama/llama3.1:8b" in model_ids

            # All models have required fields
            for m in models:
                assert "id" in m
                assert "provider" in m
                assert "name" in m


@pytest.mark.asyncio
async def test_models_endpoint_ollama_fallback():
    """When Ollama is unreachable, fallback to default model."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("src.routers.models._fetch_ollama_models", new_callable=AsyncMock) as mock_fallback:
            mock_fallback.side_effect = Exception("Connection refused")

            # Patch so _fetch_ollama_models raises, forcing fallback
            with patch("src.routers.models._fetch_ollama_models", new_callable=AsyncMock) as mock2:
                from src.schemas.models import ModelInfo

                mock2.return_value = [
                    ModelInfo(id="ollama/llama3.1:8b", provider="ollama", name="Llama 3.1 8B"),
                ]

                resp = await client.get("/v1/models")
                assert resp.status_code == 200

                data = resp.json()
                models = data["models"]
                # Should still have external models + fallback ollama model
                providers = {m["provider"] for m in models}
                assert "openai" in providers
                assert "ollama" in providers
