"""LangGraph agent graph with wizard-generated security gates.

Graph flow:
  route_tool → pre_tool_gate → (execute | blocked | confirmation)
                                   ↓
                              post_tool_gate → response → END

╔══════════════════════════════════════════════════════════════════╗
║  AI PROTECTOR — Integration Example (LangGraph)                ║
║                                                                ║
║  This file shows how AI Protector security gates are wired     ║
║  into a LangGraph StateGraph. Look for sections marked with:   ║
║                                                                ║
║    # ═══ AI PROTECTOR ═══                                      ║
║                                                                ║
║  Key integration points:                                       ║
║    1. Import PreToolGate, PostToolGate from protection.py      ║
║    2. pre_tool_gate_node  — RBAC + rate-limit check            ║
║    3. post_tool_gate_node — PII + injection scan on output     ║
║    4. Conditional routing  — block / confirm / execute          ║
║    5. Graph wiring — gates inserted between router & executor  ║
╚══════════════════════════════════════════════════════════════════╝
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

# ═══ AI PROTECTOR — Import security gates ═══════════════════════
# PreToolGate: checks RBAC permissions + rate limits BEFORE tool runs
# PostToolGate: scans tool output for PII, injection AFTER tool runs
# Both are configured by wizard-generated YAML (rbac.yaml, limits.yaml, policy.yaml)
from protection import PreToolGate, PostToolGate  # noqa: E402
# ═══════════════════════════════════════════════════════════════════


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
    no_match: bool
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


# ═══ AI PROTECTOR — Pre-Tool Gate (RBAC + Limits) ═══════════════
#
# This node runs BEFORE the tool executes. It checks:
#   1. RBAC: Does this role have permission to use this tool?
#   2. Rate Limits: Has the role exceeded max calls for this session?
#   3. Confirmation: Does this tool require explicit user confirmation?
#
# If blocked → flow goes to blocked_response_node (tool never runs)
# If confirm → flow goes to confirmation_node (asks user to confirm)
# If allowed → flow continues to tool_executor_node
#
def pre_tool_gate_node(state: AgentState) -> dict[str, Any]:
    """Pre-tool security check: RBAC + limits."""
    gate = PreToolGate()  # ← AI Protector gate, configured by wizard YAML
    tool = state.get("tool")
    role = state.get("role", "user")

    if not tool:
        return {
            "final_response": (
                "I couldn't match your request to a supported action.\n"
                "Try asking about: orders, users, products — or use "
                "one of the quick action buttons below."
            ),
            "blocked": False,
            "no_match": True,
            "gate_log": [
                {
                    "gate": "router",
                    "decision": "no_match",
                    "reason": "No tool matched the user message",
                }
            ],
        }

    # AI Protector: check RBAC permission + rate limits for this role/tool
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


# ═══════════════════════════════════════════════════════════════════


def tool_executor_node(state: AgentState) -> dict[str, Any]:
    """Execute the tool and capture output."""
    tool = state.get("tool", "")
    args = state.get("tool_args") or {}
    output = execute_tool(tool, args)
    return {"tool_output": output}


# ═══ AI PROTECTOR — Post-Tool Gate (PII + Injection Scan) ═══════
#
# This node runs AFTER the tool executes. It scans the output for:
#   1. PII: emails, phone numbers, personal data
#   2. Injection: SQL injection, prompt injection patterns
#
# Findings are logged but the response still goes through.
# In ENFORCE mode, flagged content would be redacted or blocked.
#
def post_tool_gate_node(state: AgentState) -> dict[str, Any]:
    """Post-tool scan: PII, injection detection."""
    gate = PostToolGate()  # ← AI Protector gate, uses policy.yaml scanners config
    output = state.get("tool_output", "")

    # AI Protector: scan output for sensitive data and injection patterns
    result = gate.scan(output)

    log_entry = {
        "gate": "post_tool",
        "decision": "clean" if result["clean"] else "flagged",
        "findings": result["findings"],
    }
    gate_log = list(state.get("gate_log", [])) + [log_entry]

    return {"post_gate_result": result, "gate_log": gate_log}


# ═══════════════════════════════════════════════════════════════════


def response_node(state: AgentState) -> dict[str, Any]:
    """Build final response."""
    return {"final_response": state.get("tool_output", ""), "blocked": False}


def blocked_response_node(state: AgentState) -> dict[str, Any]:
    """Build blocked response (real security block — RBAC or limits)."""
    pre_result = state.get("pre_gate_result") or {}
    reason = pre_result.get("reason", "Access denied by security policy")
    return {
        "final_response": f"\u26d4 Security block: {reason}",
        "blocked": True,
    }


def no_match_response_node(state: AgentState) -> dict[str, Any]:
    """Pass-through for routing miss — final_response already set."""
    return {}


def confirmation_node(state: AgentState) -> dict[str, Any]:
    """Build confirmation-required response."""
    tool = state.get("tool", "unknown")
    reason = state.get("pre_gate_result", {}).get("reason", "Confirmation required")
    return {
        "final_response": f"Tool '{tool}' requires confirmation. {reason}",
        "requires_confirmation": True,
        "blocked": False,
    }


# ═══ AI PROTECTOR — Conditional Routing ══════════════════════════
#
# This function reads the pre-tool gate's decision and routes the
# graph accordingly:
#   - "blocked"      → tool never executes, user sees BLOCKED message
#   - "confirmation" → tool paused, user must confirm before execution
#   - "execute"      → tool runs, then post-tool gate scans output
#


def after_pre_gate(state: AgentState) -> str:
    """Route after pre-tool gate based on decision."""
    # Routing miss — friendly info, NOT a security block
    if state.get("no_match"):
        return "no_match"
    result = state.get("pre_gate_result")
    if result is None:
        return "blocked"
    if not result.get("allowed", False):
        return "blocked"
    if result.get("requires_confirmation") and not state.get("confirmed"):
        return "confirmation"
    return "execute"


# ═══════════════════════════════════════════════════════════════════


# ── Build graph ─────────────────────────────────────────────────


# ═══ AI PROTECTOR — Graph Wiring ════════════════════════════════
#
# This is where security gates are wired into the LangGraph:
#
#   route_tool ──→ pre_tool_gate ──→ [conditional] ──→ tool_executor
#                                  │                       │
#                                  ├─→ blocked_response    ↓
#                                  ├─→ no_match_response  post_tool_gate
#                                  └─→ confirmation        │
#                                                          ↓
#                                                       response
#
# Without AI Protector, the graph would be:
#   route_tool → tool_executor → response → END
#
# AI Protector adds pre_tool_gate and post_tool_gate as mandatory
# nodes, with conditional routing for block/confirm decisions.
#
def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("route_tool", route_tool_node)
    graph.add_node("pre_tool_gate", pre_tool_gate_node)  # ← AI Protector
    graph.add_node("tool_executor", tool_executor_node)
    graph.add_node("post_tool_gate", post_tool_gate_node)  # ← AI Protector
    graph.add_node("response", response_node)
    graph.add_node("blocked_response", blocked_response_node)  # ← AI Protector
    graph.add_node("no_match_response", no_match_response_node)  # ← AI Protector
    graph.add_node("confirmation", confirmation_node)  # ← AI Protector

    graph.set_entry_point("route_tool")
    # AI Protector: security gate runs after routing, before execution
    graph.add_edge("route_tool", "pre_tool_gate")
    graph.add_conditional_edges(
        "pre_tool_gate",
        after_pre_gate,  # ← AI Protector: routes to block/confirm/execute/no_match
        {
            "execute": "tool_executor",
            "blocked": "blocked_response",
            "no_match": "no_match_response",
            "confirmation": "confirmation",
        },
    )
    # AI Protector: post-tool scan runs after execution
    graph.add_edge("tool_executor", "post_tool_gate")
    graph.add_edge("post_tool_gate", "response")
    graph.add_edge("response", END)
    graph.add_edge("blocked_response", END)
    graph.add_edge("no_match_response", END)
    graph.add_edge("confirmation", END)

    return graph


# ═══════════════════════════════════════════════════════════════════


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
