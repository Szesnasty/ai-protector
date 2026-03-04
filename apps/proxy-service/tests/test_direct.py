"""Tests for POST /v1/chat/direct endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_direct_returns_response():
    """POST /v1/chat/direct bypasses pipeline and returns LLM response."""
    mock_llm_resp = MagicMock()
    mock_llm_resp.choices = [
        MagicMock(
            message=MagicMock(role="assistant", content="Hello world"),
            finish_reason="stop",
        )
    ]
    mock_llm_resp.usage = MagicMock(prompt_tokens=5, completion_tokens=3, total_tokens=8)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("src.routers.direct.llm_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_llm_resp

            resp = await client.post(
                "/v1/chat/direct",
                json={
                    "model": "llama3.1:8b",
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            assert resp.status_code == 200

            data = resp.json()
            assert data["choices"][0]["message"]["content"] == "Hello world"

            assert resp.headers.get("x-decision") == "DIRECT"
            assert resp.headers.get("x-risk-score") == "0.00"

            mock_llm.assert_called_once()


@pytest.mark.asyncio
async def test_direct_streaming():
    """POST /v1/chat/direct streams SSE tokens without pipeline."""

    async def mock_stream():
        for token in ["Hello", " ", "world"]:
            chunk = MagicMock()
            chunk.choices = [
                MagicMock(
                    delta=MagicMock(role=None, content=token),
                    finish_reason=None,
                )
            ]
            yield chunk
        final = MagicMock()
        final.choices = [
            MagicMock(
                delta=MagicMock(role=None, content=None),
                finish_reason="stop",
            )
        ]
        yield final

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("src.routers.direct.llm_completion", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_stream()

            resp = await client.post(
                "/v1/chat/direct",
                json={
                    "model": "llama3.1:8b",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": True,
                },
            )
            assert resp.status_code == 200
            assert resp.headers.get("x-decision") == "DIRECT"

            body = resp.text
            assert "data: " in body
            assert "data: [DONE]" in body


@pytest.mark.asyncio
async def test_direct_disabled():
    """POST /v1/chat/direct returns 403 when disabled."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("src.routers.direct.get_settings") as mock_settings:
            s = MagicMock()
            s.enable_direct_endpoint = False
            mock_settings.return_value = s

            resp = await client.post(
                "/v1/chat/direct",
                json={
                    "model": "llama3.1:8b",
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            assert resp.status_code == 403
