"""LLMCallNode — call LLM through proxy-service via LiteLLM."""

from __future__ import annotations

import json
import os
import time

import structlog
from litellm import acompletion
from litellm.exceptions import APIError

from src.agent.state import AgentState
from src.agent.tools.registry import get_tools_description
from src.config import get_settings

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are a helpful Customer Support Copilot for an online store.
You help customers with their questions about orders, products, returns, shipping, and more.

You have access to the following tools (already called for you — results are included below):
{tools_description}

IMPORTANT RULES:
- Be helpful, professional, and concise.
- Use the tool results provided to answer the user's question accurately.
- If no tool results are available, answer based on general knowledge or say you don't have the information.
- Never make up order numbers, tracking URLs, or specific data — use only what the tools provide.
- If a tool was denied due to access restrictions, politely explain you don't have access to that information.
"""


def _build_messages(state: AgentState) -> list[dict[str, str]]:
    """Build the message list for the LLM call."""
    allowed_tools = state.get("allowed_tools", [])
    tools_desc = get_tools_description(allowed_tools)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(tools_description=tools_desc)},
    ]

    # Add chat history
    for msg in state.get("chat_history", []):
        messages.append(msg)

    # Add current user message
    messages.append({"role": "user", "content": state.get("message", "")})

    # Add tool results as context
    tool_calls = state.get("tool_calls", [])
    if tool_calls:
        tool_context_parts = []
        for tc in tool_calls:
            status = "✅" if tc["allowed"] else "❌ DENIED"
            tool_context_parts.append(f"[Tool: {tc['tool']} {status}]\n{tc['result']}")

        tool_context = "\n\n".join(tool_context_parts)
        messages.append({
            "role": "system",
            "content": f"Tool execution results:\n\n{tool_context}\n\nUse these results to answer the user.",
        })

    return messages


async def llm_call_node(state: AgentState) -> AgentState:
    """Call LLM through the proxy-service firewall."""
    settings = get_settings()

    # Silence LiteLLM logs
    os.environ.setdefault("LITELLM_LOG", settings.litellm_log_level)

    messages = _build_messages(state)
    session_id = state.get("session_id", "unknown")
    policy = state.get("policy", settings.default_policy)

    firewall_decision: dict = {
        "decision": "UNKNOWN",
        "risk_score": 0.0,
        "intent": "",
        "risk_flags": {},
    }

    start = time.perf_counter()

    try:
        response = await acompletion(
            model=f"ollama/{settings.default_model}",
            messages=messages,
            api_base=settings.proxy_base_url,
            extra_headers={
                "x-client-id": f"agent-{session_id}",
                "x-policy": policy,
            },
            temperature=settings.default_temperature,
            max_tokens=settings.default_max_tokens,
            timeout=120,
        )

        llm_text = response.choices[0].message.content or ""

        # Try to extract firewall headers from response
        hidden = getattr(response, "_hidden_params", {})
        addl_headers = hidden.get("additional_headers", {}) if isinstance(hidden, dict) else {}
        if addl_headers:
            firewall_decision = {
                "decision": addl_headers.get("x-decision", "ALLOW"),
                "risk_score": float(addl_headers.get("x-risk-score", "0")),
                "intent": addl_headers.get("x-intent", ""),
                "risk_flags": {},
            }
        else:
            firewall_decision["decision"] = "ALLOW"

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info("llm_call_ok", elapsed_ms=elapsed_ms, response_len=len(llm_text))

        return {
            **state,
            "llm_messages": messages,
            "llm_response": llm_text,
            "firewall_decision": firewall_decision,
        }

    except APIError as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.warning("llm_call_blocked", status=e.status_code, elapsed_ms=elapsed_ms)

        if e.status_code == 403:
            # Firewall BLOCK — parse error body
            try:
                body = json.loads(str(e.message)) if isinstance(e.message, str) else {}
            except (json.JSONDecodeError, TypeError):
                body = {}

            blocked_reason = "Request blocked by security policy."
            if isinstance(body, dict):
                error_obj = body.get("error", {})
                if isinstance(error_obj, dict):
                    blocked_reason = error_obj.get("message", blocked_reason)

                firewall_decision = {
                    "decision": "BLOCK",
                    "risk_score": body.get("risk_score", 1.0),
                    "risk_flags": body.get("risk_flags", {}),
                    "intent": body.get("intent", ""),
                    "blocked_reason": blocked_reason,
                }

            return {
                **state,
                "llm_messages": messages,
                "llm_response": "",
                "firewall_decision": firewall_decision,
                "final_response": f"I'm sorry, but I can't process that request. {blocked_reason}",
            }

        # Other API errors
        error_msg = f"LLM service error: {e}"
        return {
            **state,
            "llm_messages": messages,
            "llm_response": "",
            "firewall_decision": firewall_decision,
            "errors": [*state.get("errors", []), error_msg],
            "final_response": "I'm experiencing technical difficulties. Please try again.",
        }

    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.error("llm_call_error", error=str(e), elapsed_ms=elapsed_ms)

        return {
            **state,
            "llm_messages": messages,
            "llm_response": "",
            "firewall_decision": firewall_decision,
            "errors": [*state.get("errors", []), str(e)],
            "final_response": "I'm experiencing technical difficulties. Please try again.",
        }
