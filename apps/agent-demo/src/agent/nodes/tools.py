"""ToolRouterNode + ToolExecutorNode — plan and execute tool calls."""

from __future__ import annotations

import json
import re

import structlog

from src.agent.state import AgentState, ToolCallRecord
from src.agent.tools.registry import execute_tool

logger = structlog.get_logger()


def _select_tools_for_intent(state: AgentState) -> list[dict]:
    """Select which tools to call based on intent and message content.

    Returns a list of tool call plans: [{"tool": name, "args": {...}}].
    This is a deterministic router — no LLM needed.
    """
    intent = state.get("intent", "unknown")
    message = state.get("message", "").lower()
    allowed = state.get("allowed_tools", [])
    plans: list[dict] = []

    if intent == "order_query":
        # Extract order ID from message
        order_match = re.search(r"ord-\d{3}", message)
        order_id = order_match.group(0) if order_match else ""
        if "getOrderStatus" in allowed:
            plans.append({"tool": "getOrderStatus", "args": {"order_id": order_id or "unknown"}})

    elif intent == "knowledge_search":
        if "searchKnowledgeBase" in allowed:
            plans.append({"tool": "searchKnowledgeBase", "args": {"query": state.get("message", "")}})

    elif intent == "admin_action":
        # Try secrets first if allowed, also search KB for context
        if "getInternalSecrets" in allowed:
            plans.append({"tool": "getInternalSecrets", "args": {}})
        if "searchKnowledgeBase" in allowed and any(kw in message for kw in ["info", "help", "how"]):
            plans.append({"tool": "searchKnowledgeBase", "args": {"query": state.get("message", "")}})

    elif intent == "greeting":
        # No tools needed for greetings
        pass

    elif intent == "unknown":
        # Default: try KB search
        if "searchKnowledgeBase" in allowed:
            plans.append({"tool": "searchKnowledgeBase", "args": {"query": state.get("message", "")}})

    return plans


def tool_router_node(state: AgentState) -> AgentState:
    """Plan which tools to call based on intent and role."""
    plans = _select_tools_for_intent(state)

    logger.info("tool_router_node", tool_count=len(plans), tools=[p["tool"] for p in plans])

    return {
        **state,
        "tool_plan": plans,
    }


def tool_executor_node(state: AgentState) -> AgentState:
    """Execute planned tool calls and collect results.

    Only executes tools that passed the pre-tool gate (tool_plan is
    already filtered by pre_tool_gate_node). The RBAC check here is
    kept as a safety net.
    """
    plans = state.get("tool_plan", [])
    allowed = state.get("allowed_tools", [])
    tool_calls: list[ToolCallRecord] = list(state.get("tool_calls", []))
    iterations = state.get("iterations", 0)

    for plan in plans:
        tool_name = plan["tool"]
        args = plan.get("args", {})

        # Safety net — pre_tool_gate should have already filtered,
        # but double-check RBAC as defense in depth.
        if tool_name not in allowed:
            tool_calls.append({
                "tool": tool_name,
                "args": args,
                "result": f"Access denied: {tool_name} is not available for your role.",
                "allowed": False,
            })
            logger.warning("tool_denied", tool=tool_name, role=state.get("user_role"))
            continue

        try:
            result = execute_tool(tool_name, args)
            tool_calls.append({
                "tool": tool_name,
                "args": args,
                "result": result,
                "allowed": True,
            })
            logger.info("tool_executed", tool=tool_name, result_len=len(result))
        except Exception as e:
            error_msg = f"Tool error: {e}"
            tool_calls.append({
                "tool": tool_name,
                "args": args,
                "result": error_msg,
                "allowed": True,
            })
            logger.error("tool_error", tool=tool_name, error=str(e))

    return {
        **state,
        "tool_calls": tool_calls,
        "iterations": iterations + 1,
    }
