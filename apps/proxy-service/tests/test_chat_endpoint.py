"""Tests for POST /v1/chat/completions endpoint."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def client():
    """Async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _fake_llm_response(content: str = "Hello!") -> SimpleNamespace:
    """Build a fake non-streaming LiteLLM response."""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(role="assistant", content=content),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3, total_tokens=8),
    )


async def _fake_stream_response():
    """Async generator mimicking LiteLLM streaming."""
    chunks = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(role="assistant", content=None),
                    finish_reason=None,
                )
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(role=None, content="Hi"),
                    finish_reason=None,
                )
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(role=None, content="!"),
                    finish_reason="stop",
                )
            ]
        ),
    ]
    for chunk in chunks:
        yield chunk


CHAT_BODY = {"messages": [{"role": "user", "content": "Say hello"}]}


class TestNonStreaming:
    """Non-streaming chat completion tests."""

    @pytest.mark.asyncio
    @patch("src.routers.chat.llm_completion", new_callable=AsyncMock)
    @patch("src.services.request_logger.log_request", new_callable=AsyncMock)
    async def test_returns_openai_shape(self, mock_log, mock_llm, client: AsyncClient):
        mock_llm.return_value = _fake_llm_response()

        resp = await client.post("/v1/chat/completions", json=CHAT_BODY)

        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert data["choices"][0]["message"]["content"] == "Hello!"
        assert data["usage"]["total_tokens"] == 8
        assert data["id"].startswith("chatcmpl-")

    @pytest.mark.asyncio
    @patch("src.routers.chat.llm_completion", new_callable=AsyncMock)
    @patch("src.services.request_logger.log_request", new_callable=AsyncMock)
    async def test_correlation_id_header(self, mock_log, mock_llm, client: AsyncClient):
        mock_llm.return_value = _fake_llm_response()

        resp = await client.post("/v1/chat/completions", json=CHAT_BODY)
        assert "x-correlation-id" in resp.headers

    @pytest.mark.asyncio
    @patch("src.routers.chat.llm_completion", new_callable=AsyncMock)
    @patch("src.services.request_logger.log_request", new_callable=AsyncMock)
    async def test_accepts_custom_headers(self, mock_log, mock_llm, client: AsyncClient):
        mock_llm.return_value = _fake_llm_response()

        resp = await client.post(
            "/v1/chat/completions",
            json=CHAT_BODY,
            headers={"x-client-id": "test-client", "x-policy": "strict"},
        )
        assert resp.status_code == 200


class TestStreaming:
    """SSE streaming tests."""

    @pytest.mark.asyncio
    @patch("src.routers.chat.llm_completion", new_callable=AsyncMock)
    @patch("src.services.request_logger.log_request", new_callable=AsyncMock)
    async def test_sse_format(self, mock_log, mock_llm, client: AsyncClient):
        mock_llm.return_value = _fake_stream_response()

        body = {**CHAT_BODY, "stream": True}
        resp = await client.post("/v1/chat/completions", json=body)

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        text = resp.text
        lines = [ln for ln in text.split("\n") if ln.startswith("data:")]
        assert len(lines) >= 2  # at least one chunk + [DONE]
        assert lines[-1] == "data: [DONE]"

    @pytest.mark.asyncio
    @patch("src.routers.chat.llm_completion", new_callable=AsyncMock)
    @patch("src.services.request_logger.log_request", new_callable=AsyncMock)
    async def test_stream_chunks_are_json(self, mock_log, mock_llm, client: AsyncClient):
        mock_llm.return_value = _fake_stream_response()
        import json

        body = {**CHAT_BODY, "stream": True}
        resp = await client.post("/v1/chat/completions", json=body)

        text = resp.text
        for line in text.split("\n"):
            if line.startswith("data:") and line != "data: [DONE]":
                payload = line[len("data: "):]
                chunk = json.loads(payload)
                assert chunk["object"] == "chat.completion.chunk"
                assert "choices" in chunk


class TestErrorHandling:
    """Error response tests."""

    @pytest.mark.asyncio
    @patch("src.routers.chat.llm_completion", new_callable=AsyncMock)
    async def test_upstream_error_returns_502(self, mock_llm, client: AsyncClient):
        from src.llm.exceptions import LLMUpstreamError

        mock_llm.side_effect = LLMUpstreamError("Ollama is down")

        resp = await client.post("/v1/chat/completions", json=CHAT_BODY)

        assert resp.status_code == 502
        data = resp.json()
        assert data["error"]["type"] == "upstream_error"

    @pytest.mark.asyncio
    @patch("src.routers.chat.llm_completion", new_callable=AsyncMock)
    async def test_model_not_found_returns_404(self, mock_llm, client: AsyncClient):
        from src.llm.exceptions import LLMModelNotFoundError

        mock_llm.side_effect = LLMModelNotFoundError("no such model")

        resp = await client.post("/v1/chat/completions", json=CHAT_BODY)

        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["type"] == "model_not_found"

    @pytest.mark.asyncio
    async def test_invalid_body_returns_422(self, client: AsyncClient):
        resp = await client.post("/v1/chat/completions", json={"messages": []})
        assert resp.status_code == 422
