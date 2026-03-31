"""Tests for json_text_extractor — dot-notation path extraction."""

from __future__ import annotations

import pytest

from src.red_team.engine.json_text_extractor import extract_text, detect_text_paths


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


class TestTopLevelKey:
    def test_simple_string(self):
        assert extract_text({"text": "hello"}, ["text"]) == "hello"

    def test_numeric_value_stringified(self):
        assert extract_text({"count": 42}, ["count"]) == "42"

    def test_missing_key_returns_empty(self):
        assert extract_text({"text": "hello"}, ["missing"]) == ""


class TestNestedKeys:
    def test_two_levels(self):
        data = {"data": {"result": "ok"}}
        assert extract_text(data, ["data.result"]) == "ok"

    def test_three_levels(self):
        data = {"a": {"b": {"c": "deep"}}}
        assert extract_text(data, ["a.b.c"]) == "deep"

    def test_missing_intermediate_returns_empty(self):
        data = {"a": {"x": 1}}
        assert extract_text(data, ["a.b.c"]) == ""


class TestArrayWildcard:
    def test_flat_array(self):
        data = {"items": ["a", "b", "c"]}
        assert extract_text(data, ["items.*"]) == "a\nb\nc"

    def test_nested_array_objects(self):
        data = {"choices": [{"text": "one"}, {"text": "two"}]}
        assert extract_text(data, ["choices.*.text"]) == "one\ntwo"

    def test_empty_array(self):
        data = {"items": []}
        assert extract_text(data, ["items.*"]) == ""

    def test_wildcard_on_dict_iterates_values(self):
        data = {"map": {"a": "alpha", "b": "beta"}}
        result = extract_text(data, ["map.*"])
        assert "alpha" in result
        assert "beta" in result


class TestMultiplePaths:
    def test_two_paths_joined(self):
        data = {"title": "Hello", "body": "World"}
        result = extract_text(data, ["title", "body"])
        assert result == "Hello\nWorld"

    def test_first_path_matches_second_misses(self):
        data = {"title": "Hello"}
        assert extract_text(data, ["title", "body"]) == "Hello"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_paths_list(self):
        assert extract_text({"a": 1}, []) == ""

    def test_none_data(self):
        assert extract_text(None, ["a"]) == ""

    def test_string_data(self):
        assert extract_text("just a string", ["a"]) == ""

    def test_empty_string_values_skipped(self):
        data = {"a": "", "b": "ok"}
        assert extract_text(data, ["a", "b"]) == "ok"

    def test_none_value_skipped(self):
        data = {"a": None, "b": "ok"}
        assert extract_text(data, ["a", "b"]) == "ok"

    def test_boolean_stringified(self):
        data = {"flag": True}
        assert extract_text(data, ["flag"]) == "True"

    def test_deeply_nested_array(self):
        data = {
            "data": {
                "results": [
                    {"items": [{"content": "x"}, {"content": "y"}]},
                    {"items": [{"content": "z"}]},
                ]
            }
        }
        result = extract_text(data, ["data.results.*.items.*.content"])
        assert result == "x\ny\nz"


# ---------------------------------------------------------------------------
# detect_text_paths — auto-detection
# ---------------------------------------------------------------------------


class TestDetectTextPaths:
    def test_simple_flat(self):
        data = {"response": "This is a longer AI response text."}
        paths = detect_text_paths(data)
        assert paths == ["response"]

    def test_nested(self):
        data = {"data": {"result": {"text": "Some long answer from the AI."}}}
        paths = detect_text_paths(data)
        assert "data.result.text" in paths

    def test_openai_format(self):
        data = {
            "choices": [
                {"message": {"content": "Hello! How can I help you today?", "role": "assistant"}, "index": 0}
            ],
            "model": "gpt-4",
            "id": "chatcmpl-abc",
        }
        paths = detect_text_paths(data)
        assert paths[0] == "choices.*.message.content"

    def test_anthropic_format(self):
        data = {
            "content": [{"type": "text", "text": "Here is my response to your question."}],
            "model": "claude-3",
            "id": "msg_abc",
        }
        paths = detect_text_paths(data)
        assert "content.*.text" in paths

    def test_longest_first(self):
        data = {"short": "hi there!", "long_answer": "A" * 100}
        paths = detect_text_paths(data)
        assert paths[0] == "long_answer"

    def test_ignores_short_strings(self):
        data = {"id": "abc", "code": "200", "ok": "yes"}
        paths = detect_text_paths(data)
        assert paths == []

    def test_max_paths_limit(self):
        data = {f"field_{i}": f"long enough text {i}" for i in range(20)}
        paths = detect_text_paths(data, max_paths=3)
        assert len(paths) <= 3

    def test_array_wildcard_deduplication(self):
        data = {"items": [{"text": "hello world"}, {"text": "goodbye world"}]}
        paths = detect_text_paths(data)
        assert paths.count("items.*.text") == 1

    def test_non_dict_input(self):
        assert detect_text_paths("just a string") == []
        assert detect_text_paths(42) == []
        assert detect_text_paths(None) == []

    def test_empty_dict(self):
        assert detect_text_paths({}) == []
