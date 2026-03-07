"""Mock LLM for agent-demo in demo mode.

Returns responses that trigger tool calls or summarise tool results,
matching the agent's expected LLM behaviour.  This allows the full
agent graph (intent → policy → tools → response) to execute without a
real LLM backend.

Used when ``MODE=demo`` and no ``x-api-key`` is provided.
"""

from __future__ import annotations

import json
import time
from typing import Any

from src.agent.state import AgentState

# ── Tool-call triggers ───────────────────────────────────────

# Keywords in the user message that should trigger a specific tool call.
TOOL_CALL_TRIGGERS: dict[str, dict[str, Any]] = {
    "order": {
        "name": "getOrderStatus",
        "arguments": {"order_id": "ORD-12345"},
    },
    "status": {
        "name": "getOrderStatus",
        "arguments": {"order_id": "ORD-12345"},
    },
    "knowledge": {
        "name": "searchKnowledgeBase",
        "arguments": {"query": "return policy"},
    },
    "return": {
        "name": "searchKnowledgeBase",
        "arguments": {"query": "return policy"},
    },
    "policy": {
        "name": "searchKnowledgeBase",
        "arguments": {"query": "return policy"},
    },
    "faq": {
        "name": "searchKnowledgeBase",
        "arguments": {"query": "FAQ"},
    },
}

# ── Summary responses (after tool results) ───────────────────

SUMMARY_TEMPLATES: list[str] = [
    "Based on the information I found: {tool_result}",
    "Here's what I found for you: {tool_result}",
]

GENERAL_RESPONSES: list[str] = [
    (
        "Hello! I'm the AI Protector agent demo. I can look up order statuses "
        "and search our knowledge base. Try asking about an order or a return "
        "policy \u2014 and watch the security pipeline in the trace panel!"
    ),
    (
        "Hi there! This is demo mode \u2014 the agent graph, RBAC, tool gates, "
        "and firewall pipeline all run for real. Ask me about an order or "
        "search the knowledge base."
    ),
]

MOCK_MODEL_ID = "mock-demo-agent"


def _last_user_content(state: AgentState) -> str:
    """Extract the last user message content (lowercased)."""
    messages = state.get("messages") or []
    for m in reversed(messages):
        if m.get("role") == "user":
            return (m.get("content") or "").lower()
    return ""


def _has_tool_results(state: AgentState) -> bool:
    """Check if the conversation already contains tool results."""
    messages = state.get("messages") or []
    return any(m.get("role") == "tool" for m in messages)


def _detect_tool_call(user_content: str) -> dict[str, Any] | None:
    """Return a tool call dict if the user message matches a trigger keyword."""
    for keyword, tool_spec in TOOL_CALL_TRIGGERS.items():
        if keyword in user_content:
            return tool_spec
    return None


def _build_mock_response(
    content: str,
    *,
    tool_calls: list[dict[str, Any]] | None = None,
) -> Any:
    """Build a mock object that mimics a LiteLLM response.

    The agent code accesses ``response.choices[0].message.content`` and
    reads ``_hidden_params`` for firewall headers.
    """

    class _Msg:
        def __init__(self, c: str, tc: list | None) -> None:
            self.content = c
            self.tool_calls = tc
            self.role = "assistant"

    class _Choice:
        def __init__(self, msg: _Msg) -> None:
            self.message = msg
            self.finish_reason = "tool_calls" if msg.tool_calls else "stop"

    class _Usage:
        def __init__(self, p: int, c: int) -> None:
            self.prompt_tokens = p
            self.completion_tokens = c
            self.total_tokens = p + c

    class _Response:
        def __init__(self, choice: _Choice, usage: _Usage) -> None:
            self.choices = [choice]
            self.usage = usage
            self.model = MOCK_MODEL_ID
            self.id = f"chatcmpl-mock-agent-{int(time.time())}"
            self._hidden_params = {
                "additional_headers": {
                    "x-decision": "ALLOW",
                    "x-risk-score": "0.0",
                    "x-intent": "qa",
                }
            }

    prompt_tokens = 50  # Rough estimate
    completion_tokens = len(content.split()) if content else 5
    return _Response(
        _Choice(_Msg(content, tool_calls)),
        _Usage(prompt_tokens, completion_tokens),
    )


def mock_agent_llm(state: AgentState) -> AgentState:
    """Generate a mock LLM response for the agent graph.

    Decision logic:
    1. If tool results are present → summarise them.
    2. If the user message matches a tool trigger → return a tool_call.
    3. Otherwise → return a friendly general response.
    """
    import random  # noqa: S311 — deterministic demo, not crypto

    user_content = _last_user_content(state)
    start = time.perf_counter()

    # ── Case 1: tool results already in context → summarise ──
    if _has_tool_results(state):
        # Find the last tool result
        messages = state.get("messages") or []
        tool_result = ""
        for m in reversed(messages):
            if m.get("role") == "tool":
                tool_result = m.get("content", "")
                break
        template = random.choice(SUMMARY_TEMPLATES)
        content = template.format(tool_result=tool_result[:200])
        response = _build_mock_response(content)

    # ── Case 2: user message triggers a tool call ────────────
    elif tool_spec := _detect_tool_call(user_content):
        tool_call_obj = {
            "id": f"call_mock_{int(time.time())}",
            "type": "function",
            "function": {
                "name": tool_spec["name"],
                "arguments": json.dumps(tool_spec["arguments"]),
            },
        }
        response = _build_mock_response(
            content="",
            tool_calls=[tool_call_obj],
        )

    # ── Case 3: general response ─────────────────────────────
    else:
        content = random.choice(GENERAL_RESPONSES)
        response = _build_mock_response(content)

    int((time.perf_counter() - start) * 1000)

    # Build minimal firewall decision
    firewall_decision = {
        "decision": "ALLOW",
        "risk_score": 0.0,
        "intent": "qa",
        "risk_flags": {},
    }

    return {
        **state,
        "llm_messages": state.get("messages", []),
        "llm_response": response.choices[0].message.content or "",
        "firewall_decision": firewall_decision,
        "trace": state.get("trace", []),
    }
