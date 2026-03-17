"""LangGraph agent graph with wizard-generated security gates.

Graph flow:
  route_tool → pre_tool_gate → (execute | blocked | confirmation)
                                   ↓
                              post_tool_gate → response → END
"""

from __future__ import annotations

import re
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

import sys
import os

# Ensure shared tools are importable (parent of langgraph-agent/)
_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from shared.tools import execute_tool  # noqa: E402

from protection import PreToolGate, PostToolGate  # noqa: E402


# ── State schema ────────────────────────────────────────────────


class AgentState(TypedDict, total=False):
    message: str
    role: str
    tool: str | None
    tool_args: dict | None
    confirmed: bool
    gate_log: list[dict]
    # internal
    pre_gate_result: dict | None
    tool_output: str | None
    post_gate_result: dict | None
    final_response: str | None
    blocked: bool
    requires_confirmation: bool


# ── Graph nodes ─────────────────────────────────────────────────


def route_tool_node(state: AgentState) -> dict[str, Any]:
    """Route message to the appropriate tool (keyword-based)."""
    msg = state.get("message", "").lower()
    tool = state.get("tool")  # explicit tool takes priority

    if not tool:
        if any(
            w in msg
            for w in ["update order", "change order", "modify order", "zmień zamówien"]
        ):
            tool = "updateOrder"
        elif any(w in msg for w in ["order", "orders", "zamówien"]):
            tool = "getOrders"
        elif any(
            w in msg
            for w in ["update user", "change user", "modify user", "zmień użytkown"]
        ):
            tool = "updateUser"
        elif any(w in msg for w in ["user", "users", "użytkown"]):
            tool = "getUsers"
        elif any(w in msg for w in ["product", "search", "find", "szukaj"]):
            tool = "searchProducts"

    # Extract args
    tool_args = state.get("tool_args") or {}
    if tool and not tool_args:
        tool_args = _extract_args(msg, tool)

    return {"tool": tool, "tool_args": tool_args, "gate_log": []}


def pre_tool_gate_node(state: AgentState) -> dict[str, Any]:
    """Pre-tool security check: RBAC + limits."""
    gate = PreToolGate()
    tool = state.get("tool")
    role = state.get("role", "user")

    if not tool:
        return {
            "final_response": "No tool matched your request.",
            "blocked": True,
            "gate_log": [{"gate": "router", "decision": "no_match"}],
        }

    result = gate.check(role, tool, state.get("tool_args"))

    log_entry = {
        "gate": "pre_tool",
        "decision": result["decision"],
        "reason": result.get("reason"),
        "tool": tool,
        "role": role,
    }
    gate_log = list(state.get("gate_log", [])) + [log_entry]

    return {"pre_gate_result": result, "gate_log": gate_log}


def tool_executor_node(state: AgentState) -> dict[str, Any]:
    """Execute the tool and capture output."""
    tool = state.get("tool", "")
    args = state.get("tool_args") or {}
    output = execute_tool(tool, args)
    return {"tool_output": output}


def post_tool_gate_node(state: AgentState) -> dict[str, Any]:
    """Post-tool scan: PII, injection detection."""
    gate = PostToolGate()
    output = state.get("tool_output", "")
    result = gate.scan(output)

    log_entry = {
        "gate": "post_tool",
        "decision": "clean" if result["clean"] else "flagged",
        "findings": result["findings"],
    }
    gate_log = list(state.get("gate_log", [])) + [log_entry]

    return {"post_gate_result": result, "gate_log": gate_log}


def response_node(state: AgentState) -> dict[str, Any]:
    """Build final response."""
    return {"final_response": state.get("tool_output", ""), "blocked": False}


def blocked_response_node(state: AgentState) -> dict[str, Any]:
    """Build blocked response."""
    reason = state.get("pre_gate_result", {}).get("reason", "Access denied")
    return {"final_response": f"BLOCKED: {reason}", "blocked": True}


def confirmation_node(state: AgentState) -> dict[str, Any]:
    """Build confirmation-required response."""
    tool = state.get("tool", "unknown")
    reason = state.get("pre_gate_result", {}).get("reason", "Confirmation required")
    return {
        "final_response": f"Tool '{tool}' requires confirmation. {reason}",
        "requires_confirmation": True,
        "blocked": False,
    }


# ── Conditional routing ─────────────────────────────────────────


def after_pre_gate(state: AgentState) -> str:
    """Route after pre-tool gate based on decision."""
    result = state.get("pre_gate_result")
    # If no tool was matched, pre_gate_result is None → blocked
    if result is None:
        return "blocked"
    if not result.get("allowed", False):
        return "blocked"
    if result.get("requires_confirmation") and not state.get("confirmed"):
        return "confirmation"
    return "execute"


# ── Build graph ─────────────────────────────────────────────────


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("route_tool", route_tool_node)
    graph.add_node("pre_tool_gate", pre_tool_gate_node)
    graph.add_node("tool_executor", tool_executor_node)
    graph.add_node("post_tool_gate", post_tool_gate_node)
    graph.add_node("response", response_node)
    graph.add_node("blocked_response", blocked_response_node)
    graph.add_node("confirmation", confirmation_node)

    graph.set_entry_point("route_tool")
    graph.add_edge("route_tool", "pre_tool_gate")
    graph.add_conditional_edges(
        "pre_tool_gate",
        after_pre_gate,
        {
            "execute": "tool_executor",
            "blocked": "blocked_response",
            "confirmation": "confirmation",
        },
    )
    graph.add_edge("tool_executor", "post_tool_gate")
    graph.add_edge("post_tool_gate", "response")
    graph.add_edge("response", END)
    graph.add_edge("blocked_response", END)
    graph.add_edge("confirmation", END)

    return graph


_compiled = None


def get_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_graph().compile()
    return _compiled


def reset_graph():
    """Force recompilation (used after config change)."""
    global _compiled
    _compiled = None


# ── Arg extraction helper ───────────────────────────────────────


def _extract_args(message: str, tool: str) -> dict:
    """Extract basic args from message text (simplified)."""
    args: dict = {}
    if tool == "updateOrder":
        m = re.search(r"(ORD-\d+)", message, re.IGNORECASE)
        if m:
            args["order_id"] = m.group(1).upper()
        for status in ["shipped", "delivered", "cancelled", "processing", "pending"]:
            if status in message.lower():
                args["status"] = status
                break
    elif tool == "updateUser":
        m = re.search(r"(USR-\d+)", message, re.IGNORECASE)
        if m:
            args["user_id"] = m.group(1).upper()
    elif tool == "searchProducts":
        m = re.search(
            r"(?:search|find|szukaj)\s+(?:for\s+)?(.+)", message, re.IGNORECASE
        )
        if m:
            args["query"] = m.group(1).strip()
    return args
