"""LLMCallNode — call LLM through proxy-service via LiteLLM.

Uses message_builder (spec 05) for safe message construction with
role-separation, anti-spoofing delimiters and sanitization.
"""

from __future__ import annotations

import json
import os
import time

import structlog
from litellm import acompletion
from litellm.exceptions import APIError

from src.agent.security.message_builder import build_messages
from src.agent.state import AgentState
from src.config import get_settings

logger = structlog.get_logger()


async def llm_call_node(state: AgentState) -> AgentState:
    """Call LLM through the proxy-service firewall."""
    settings = get_settings()

    # Silence LiteLLM logs
    os.environ.setdefault("LITELLM_LOG", settings.litellm_log_level)

    messages = build_messages(state)
    session_id = state.get("session_id", "unknown")
    policy = state.get("policy", settings.default_policy)

    firewall_decision: dict = {
        "decision": "UNKNOWN",
        "risk_score": 0.0,
        "intent": "",
        "risk_flags": {},
    }

    start = time.perf_counter()

    model_name = state.get("model", settings.default_model)
    api_key = state.get("api_key")

    # Format model for LiteLLM: use prefix routing through proxy
    litellm_model = f"{settings.default_model_prefix}/{model_name}"

    extra_headers: dict[str, str] = {
        "x-client-id": f"agent-{session_id}",
        "x-policy": policy,
        "x-correlation-id": session_id,
    }
    if api_key:
        extra_headers["x-api-key"] = api_key

    try:
        response = await acompletion(
            model=litellm_model,
            messages=messages,
            api_base=settings.proxy_base_url,
            api_key="not-needed",
            extra_headers=extra_headers,
            temperature=settings.default_temperature,
            max_tokens=settings.default_max_tokens,
            timeout=120,
        )

        llm_text = response.choices[0].message.content or ""

        # Try to extract firewall headers from response
        # LiteLLM prefixes provider headers with "llm_provider-"
        hidden = getattr(response, "_hidden_params", {})
        addl_headers = hidden.get("additional_headers", {}) if isinstance(hidden, dict) else {}
        if addl_headers:
            # Try both raw and llm_provider- prefixed header names
            def _hdr(name: str) -> str:
                return addl_headers.get(name, addl_headers.get(f"llm_provider-{name}", ""))

            decision = _hdr("x-decision") or "ALLOW"
            risk_score_str = _hdr("x-risk-score") or "0"
            intent_val = _hdr("x-intent") or ""

            firewall_decision = {
                "decision": decision,
                "risk_score": float(risk_score_str),
                "intent": intent_val,
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
