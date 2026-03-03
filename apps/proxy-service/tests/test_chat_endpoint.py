"""Tests for POST /v1/chat/completions endpoint (with pipeline)."""

from __future__ import annotations

import json
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


# ── Helpers ──────────────────────────────────────────────────────────────


def _pipeline_state(
    *,
    decision: str = "ALLOW",
    intent: str = "qa",
    risk_score: float = 0.1,
    risk_flags: dict | None = None,
    blocked_reason: str | None = None,
    llm_response=None,
    modified_messages: list[dict] | None = None,
    tokens_in: int = 5,
    tokens_out: int = 3,
) -> dict:
    """Build a fake pipeline state dict."""
    if llm_response is None:
        llm_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(role="assistant", content="Hello!"),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=tokens_in,
                completion_tokens=tokens_out,
                total_tokens=tokens_in + tokens_out,
            ),
        )
    return {
        "decision": decision,
        "intent": intent,
        "risk_score": risk_score,
        "risk_flags": risk_flags or {},
        "blocked_reason": blocked_reason,
        "llm_response": llm_response,
        "modified_messages": modified_messages,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }


def _pre_pipeline_state(
    *,
    decision: str = "ALLOW",
    intent: str = "qa",
    risk_score: float = 0.1,
    risk_flags: dict | None = None,
    blocked_reason: str | None = None,
    modified_messages: list[dict] | None = None,
) -> dict:
    """Build a fake pre-LLM pipeline state dict."""
    return {
        "decision": decision,
        "intent": intent,
        "risk_score": risk_score,
        "risk_flags": risk_flags or {},
        "blocked_reason": blocked_reason,
        "modified_messages": modified_messages,
    }


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

# Patch targets
_PATCH_RUN = "src.routers.chat.run_pipeline"
_PATCH_PRE = "src.routers.chat.run_pre_llm_pipeline"
_PATCH_LLM = "src.routers.chat.llm_completion"


class TestNonStreaming:
    """Non-streaming chat completion tests."""

    @pytest.mark.asyncio
    @patch(_PATCH_RUN, new_callable=AsyncMock)
    async def test_clean_returns_200_openai_shape(self, mock_run, client: AsyncClient):
        mock_run.return_value = _pipeline_state()

        resp = await client.post("/v1/chat/completions", json=CHAT_BODY)

        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert data["choices"][0]["message"]["content"] == "Hello!"
        assert data["usage"]["total_tokens"] == 8
        assert data["id"].startswith("chatcmpl-")

    @pytest.mark.asyncio
    @patch(_PATCH_RUN, new_callable=AsyncMock)
    async def test_block_returns_403(self, mock_run, client: AsyncClient):
        mock_run.return_value = _pipeline_state(
            decision="BLOCK",
            blocked_reason="Injection detected",
            risk_score=0.95,
            risk_flags={"injection": 0.9},
            intent="jailbreak",
        )

        resp = await client.post("/v1/chat/completions", json=CHAT_BODY)

        assert resp.status_code == 403
        data = resp.json()
        assert data["error"]["type"] == "policy_violation"
        assert data["error"]["code"] == "blocked"
        assert data["decision"] == "BLOCK"
        assert data["risk_score"] == 0.95
        assert data["intent"] == "jailbreak"

    @pytest.mark.asyncio
    @patch(_PATCH_RUN, new_callable=AsyncMock)
    async def test_pipeline_headers_present(self, mock_run, client: AsyncClient):
        mock_run.return_value = _pipeline_state(intent="code_gen", risk_score=0.25)

        resp = await client.post("/v1/chat/completions", json=CHAT_BODY)

        assert resp.status_code == 200
        assert resp.headers["x-decision"] == "ALLOW"
        assert resp.headers["x-intent"] == "code_gen"
        assert resp.headers["x-risk-score"] == "0.25"

    @pytest.mark.asyncio
    @patch(_PATCH_RUN, new_callable=AsyncMock)
    async def test_correlation_id_header(self, mock_run, client: AsyncClient):
        mock_run.return_value = _pipeline_state()

        resp = await client.post("/v1/chat/completions", json=CHAT_BODY)
        assert "x-correlation-id" in resp.headers

    @pytest.mark.asyncio
    @patch(_PATCH_RUN, new_callable=AsyncMock)
    async def test_accepts_custom_headers(self, mock_run, client: AsyncClient):
        mock_run.return_value = _pipeline_state()

        resp = await client.post(
            "/v1/chat/completions",
            json=CHAT_BODY,
            headers={"x-client-id": "test-client", "x-policy": "strict"},
        )
        assert resp.status_code == 200


class TestStreaming:
    """SSE streaming tests."""

    @pytest.mark.asyncio
    @patch(_PATCH_LLM, new_callable=AsyncMock)
    @patch(_PATCH_PRE, new_callable=AsyncMock)
    async def test_sse_format(self, mock_pre, mock_llm, client: AsyncClient):
        mock_pre.return_value = _pre_pipeline_state()
        mock_llm.return_value = _fake_stream_response()

        body = {**CHAT_BODY, "stream": True}
        resp = await client.post("/v1/chat/completions", json=body)

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert resp.headers["x-decision"] == "ALLOW"
        assert resp.headers["x-intent"] == "qa"

        lines = [ln for ln in resp.text.split("\n") if ln.startswith("data:")]
        assert len(lines) >= 2
        assert lines[-1] == "data: [DONE]"

    @pytest.mark.asyncio
    @patch(_PATCH_LLM, new_callable=AsyncMock)
    @patch(_PATCH_PRE, new_callable=AsyncMock)
    async def test_stream_block_returns_403(self, mock_pre, mock_llm, client: AsyncClient):
        mock_pre.return_value = _pre_pipeline_state(
            decision="BLOCK",
            blocked_reason="Denylist hit",
            risk_score=0.9,
        )

        body = {**CHAT_BODY, "stream": True}
        resp = await client.post("/v1/chat/completions", json=body)

        assert resp.status_code == 403
        data = resp.json()
        assert data["error"]["type"] == "policy_violation"
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    @patch(_PATCH_LLM, new_callable=AsyncMock)
    @patch(_PATCH_PRE, new_callable=AsyncMock)
    async def test_stream_chunks_are_json(self, mock_pre, mock_llm, client: AsyncClient):
        mock_pre.return_value = _pre_pipeline_state()
        mock_llm.return_value = _fake_stream_response()

        body = {**CHAT_BODY, "stream": True}
        resp = await client.post("/v1/chat/completions", json=body)

        for line in resp.text.split("\n"):
            if line.startswith("data:") and line != "data: [DONE]":
                payload = line[len("data: "):]
                chunk = json.loads(payload)
                assert chunk["object"] == "chat.completion.chunk"
                assert "choices" in chunk


class TestErrorHandling:
    """Error response tests — LLM-level errors still work through pipeline."""

    @pytest.mark.asyncio
    @patch(_PATCH_RUN, new_callable=AsyncMock)
    async def test_upstream_error_returns_502(self, mock_run, client: AsyncClient):
        from src.llm.exceptions import LLMUpstreamError

        mock_run.side_effect = LLMUpstreamError("Ollama is down")

        resp = await client.post("/v1/chat/completions", json=CHAT_BODY)

        assert resp.status_code == 502
        data = resp.json()
        assert data["error"]["type"] == "upstream_error"

    @pytest.mark.asyncio
    @patch(_PATCH_RUN, new_callable=AsyncMock)
    async def test_model_not_found_returns_404(self, mock_run, client: AsyncClient):
        from src.llm.exceptions import LLMModelNotFoundError

        mock_run.side_effect = LLMModelNotFoundError("no such model")

        resp = await client.post("/v1/chat/completions", json=CHAT_BODY)

        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["type"] == "model_not_found"

    @pytest.mark.asyncio
    async def test_invalid_body_returns_422(self, client: AsyncClient):
        resp = await client.post("/v1/chat/completions", json={"messages": []})
        assert resp.status_code == 422
