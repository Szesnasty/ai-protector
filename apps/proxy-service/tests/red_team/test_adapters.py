"""Tests for adapter-level features: SSE stripping, deep heuristic, response body truncation."""

from __future__ import annotations

import json

from src.red_team.engine.adapters import _MAX_RESPONSE_BODY_BYTES, SimpleNormalizer
from src.red_team.engine.protocols import HttpResponse

# ===========================================================================
# SSE frame stripping
# ===========================================================================


class TestSseStripping:
    """SimpleNormalizer._strip_sse_frames extracts text from SSE bodies."""

    def test_openai_streaming_chunks(self) -> None:
        """OpenAI format: data: {"choices": [{"delta": {"content": "..."}}]}"""
        lines = [
            'data: {"choices": [{"delta": {"content": "Hello"}}]}',
            'data: {"choices": [{"delta": {"content": " world"}}]}',
            "data: [DONE]",
        ]
        result = SimpleNormalizer._strip_sse_frames("\n".join(lines))
        assert result == "Hello world"

    def test_anthropic_streaming_chunks(self) -> None:
        """Anthropic format: data: {"delta": {"text": "..."}}"""
        lines = [
            'data: {"type": "content_block_delta", "delta": {"text": "Foo"}}',
            'data: {"type": "content_block_delta", "delta": {"text": " Bar"}}',
            "data: [DONE]",
        ]
        result = SimpleNormalizer._strip_sse_frames("\n".join(lines))
        assert result == "Foo Bar"

    def test_non_json_data_lines(self) -> None:
        """Plain text data lines fall back to raw concatenation."""
        raw = "data: Hello\ndata: World\n"
        result = SimpleNormalizer._strip_sse_frames(raw)
        assert result == "HelloWorld"

    def test_empty_body_returns_raw(self) -> None:
        """Empty or no data: lines → returns original body."""
        result = SimpleNormalizer._strip_sse_frames("")
        assert result == ""

    def test_done_line_skipped(self) -> None:
        result = SimpleNormalizer._strip_sse_frames("data: [DONE]\n")
        assert result == "data: [DONE]\n"  # No payload extracted → returns raw

    def test_normalizer_detects_sse_content_type(self) -> None:
        """SSE stripping activates on text/event-stream content-type."""
        body = 'data: {"choices": [{"delta": {"content": "Hi"}}]}\ndata: [DONE]\n'
        resp = HttpResponse(
            status_code=200,
            body=body,
            headers={"content-type": "text/event-stream"},
        )
        norm = SimpleNormalizer()
        result = norm.normalize(resp, {})
        assert result.body_text == "Hi"
        assert result.provider_format in ("sse", "sse_json")

    def test_normalizer_detects_sse_data_prefix(self) -> None:
        """SSE stripping activates when body starts with 'data: '."""
        body = 'data: {"choices": [{"delta": {"content": "Hello"}}]}\ndata: [DONE]\n'
        resp = HttpResponse(status_code=200, body=body)
        norm = SimpleNormalizer()
        result = norm.normalize(resp, {})
        assert result.body_text == "Hello"


# ===========================================================================
# Deep heuristic — AI provider format auto-detection
# ===========================================================================


class TestDeepHeuristic:
    """SimpleNormalizer._try_deep_heuristic finds text in nested provider formats."""

    def test_openai_format(self) -> None:
        data = {"choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello from OpenAI"}}]}
        assert SimpleNormalizer._try_deep_heuristic(data) == "Hello from OpenAI"

    def test_anthropic_format(self) -> None:
        data = {
            "content": [{"type": "text", "text": "Hello from Anthropic"}],
            "model": "claude-3",
        }
        assert SimpleNormalizer._try_deep_heuristic(data) == "Hello from Anthropic"

    def test_gemini_format(self) -> None:
        data = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Hello from Gemini"}],
                        "role": "model",
                    }
                }
            ]
        }
        assert SimpleNormalizer._try_deep_heuristic(data) == "Hello from Gemini"

    def test_bedrock_format(self) -> None:
        data = {"results": [{"outputText": "Hello from Bedrock", "tokenCount": 5}]}
        assert SimpleNormalizer._try_deep_heuristic(data) == "Hello from Bedrock"

    def test_cohere_format(self) -> None:
        data = {"generations": [{"text": "Hello from Cohere", "id": "abc"}]}
        assert SimpleNormalizer._try_deep_heuristic(data) == "Hello from Cohere"

    def test_unknown_format_returns_empty(self) -> None:
        data = {"foo": {"bar": {"baz": "some text"}}}
        assert SimpleNormalizer._try_deep_heuristic(data) == ""

    def test_empty_dict(self) -> None:
        assert SimpleNormalizer._try_deep_heuristic({}) == ""

    def test_openai_via_full_normalizer(self) -> None:
        """Full normalizer pipeline extracts OpenAI content without configured paths."""
        body = json.dumps({"choices": [{"message": {"role": "assistant", "content": "Extracted!"}}]})
        resp = HttpResponse(status_code=200, body=body)
        norm = SimpleNormalizer()
        result = norm.normalize(resp, {})
        assert result.body_text == "Extracted!"

    def test_configured_paths_take_precedence(self) -> None:
        """Configured response_text_paths override the deep heuristic."""
        body = json.dumps(
            {
                "choices": [{"message": {"content": "From deep heuristic"}}],
                "custom_field": "From configured path",
            }
        )
        resp = HttpResponse(status_code=200, body=body)
        norm = SimpleNormalizer()
        result = norm.normalize(resp, {"response_text_paths": ["custom_field"]})
        assert result.body_text == "From configured path"


# ===========================================================================
# Response body size limit
# ===========================================================================


class TestResponseBodySizeLimit:
    """RealHttpClient truncates responses larger than _MAX_RESPONSE_BODY_BYTES."""

    def test_max_response_body_bytes_constant(self) -> None:
        """The limit is 512 KB."""
        assert _MAX_RESPONSE_BODY_BYTES == 512 * 1024

    def test_large_body_normalizer_still_works(self) -> None:
        """Even a body at the limit normalizes without error."""
        body = "x" * _MAX_RESPONSE_BODY_BYTES
        resp = HttpResponse(status_code=200, body=body)
        norm = SimpleNormalizer()
        result = norm.normalize(resp, {})
        assert len(result.body_text) == _MAX_RESPONSE_BODY_BYTES

    def test_json_in_truncated_body_falls_back_gracefully(self) -> None:
        """A truncated JSON body should still produce a body_text (raw fallback)."""
        # Create JSON that would be valid if complete, but is cut off
        inner = "a" * (_MAX_RESPONSE_BODY_BYTES + 100)
        full_json = json.dumps({"response": inner})
        truncated = full_json[:_MAX_RESPONSE_BODY_BYTES]
        resp = HttpResponse(status_code=200, body=truncated)
        norm = SimpleNormalizer()
        result = norm.normalize(resp, {})
        # Should fall back to raw body since JSON parse fails
        assert result.parsed_json is None
        assert result.body_text == truncated
