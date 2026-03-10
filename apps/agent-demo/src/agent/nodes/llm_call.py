"""LLMCallNode — call LLM through proxy-service via LiteLLM.

Uses message_builder (spec 05) for safe message construction with
role-separation, anti-spoofing delimiters and sanitization.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
import structlog
from litellm import acompletion
from litellm.exceptions import APIError

from src.agent.limits.config import get_limits_for_role
from src.agent.limits.service import get_limits_service
from src.agent.security.message_builder import build_messages
from src.agent.state import AgentState
from src.agent.trace.accumulator import TraceAccumulator
from src.config import Settings, get_settings

logger = structlog.get_logger()

# ── Provider detection rules (mirrors proxy-service/src/llm/providers.py) ──
_PROVIDER_RULES: list[tuple[str, str]] = [
    ("ollama/", "ollama"),
    ("anthropic/", "anthropic"),
    ("gemini/", "google"),
    ("mistral/", "mistral"),
    ("azure/", "azure"),
    ("gpt-", "openai"),
    ("o1", "openai"),
    ("o3", "openai"),
    ("claude-", "anthropic"),
    ("gemini-", "google"),
    ("mistral-", "mistral"),
    ("codestral", "mistral"),
]


def _resolve_direct_llm(
    model_name: str,
    api_key: str | None,
    settings: Settings,
) -> tuple[str, dict[str, Any]]:
    """Resolve model name and kwargs for a direct LLM call (bypassing proxy).

    Returns ``(litellm_model, extra_kwargs)``.  For Ollama the kwargs contain
    ``api_base``; for external providers they carry ``api_key``.
    """
    model_lower = model_name.lower()
    provider = "ollama"
    for pattern, prov in _PROVIDER_RULES:
        if model_lower.startswith(pattern):
            provider = prov
            break

    # Format model for LiteLLM (add provider prefix where required)
    if provider == "ollama" and not model_name.startswith("ollama/"):
        litellm_model = f"ollama/{model_name}"
    elif provider == "anthropic" and not model_name.startswith("anthropic/"):
        litellm_model = f"anthropic/{model_name}"
    elif provider == "google" and not model_name.startswith("gemini/"):
        litellm_model = f"gemini/{model_name}"
    elif provider == "mistral" and not model_name.startswith("mistral/"):
        litellm_model = f"mistral/{model_name}"
    else:
        litellm_model = model_name  # openai: no prefix

    if provider == "ollama":
        return litellm_model, {"api_base": settings.ollama_base_url}
    return litellm_model, {"api_key": api_key}


def _track_tokens(response: Any, state: AgentState, model: str) -> dict:
    """Extract token usage from LLM response and track in limits service.

    Returns state dict additions for token counters.
    """
    try:
        usage = getattr(response, "usage", None)
        if not usage:
            return {}

        tokens_in = getattr(usage, "prompt_tokens", 0) or 0
        tokens_out = getattr(usage, "completion_tokens", 0) or 0

        # Guard against non-integer values (e.g. from mocks)
        if not isinstance(tokens_in, (int, float)) or not isinstance(tokens_out, (int, float)):
            return {}

        tokens_in = int(tokens_in)
        tokens_out = int(tokens_out)

        if tokens_in == 0 and tokens_out == 0:
            return {}

        session_id = state.get("session_id", "")
        if not session_id:
            return {}

        limits_svc = get_limits_service()
        tracked = limits_svc.track_token_usage(session_id, tokens_in, tokens_out, model)

        # Check budget after tracking
        role = state.get("user_role", "customer")
        config = get_limits_for_role(role)
        budget_check = limits_svc.check_token_budget(session_id, config)

        result: dict = {
            "session_tokens_in": tracked["session_tokens_in"],
            "session_tokens_out": tracked["session_tokens_out"],
            "session_estimated_cost": tracked["session_estimated_cost"],
        }

        if not budget_check.allowed:
            result["limit_exceeded"] = budget_check.limit_type
            logger.warning(
                "limit_exceeded_post_llm",
                limit_type=budget_check.limit_type,
                limit_value=budget_check.limit_value,
                current_value=budget_check.current_value,
                session_id=session_id,
            )

        return result
    except (TypeError, ValueError, AttributeError):
        # Gracefully handle unexpected response shapes (e.g. mocks)
        return {}


async def _scan_via_proxy(
    *,
    proxy_base_url: str,
    session_id: str,
    policy: str,
    api_key: str | None,
    scan_messages: list[dict],
    model_name: str,
    temperature: float,
    max_tokens: int | None,
) -> dict:
    """Call POST /v1/scan and return the parsed JSON response.

    Returns a dict with at least: ``status_code``, ``decision``,
    ``risk_score``, ``risk_flags``, ``intent``, ``blocked_reason``.
    """
    scan_url = f"{proxy_base_url}/scan"
    scan_body = {
        "model": model_name,
        "messages": scan_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    scan_headers: dict[str, str] = {
        "Content-Type": "application/json",
        "x-client-id": f"agent-{session_id}",
        "x-policy": policy,
        "x-correlation-id": session_id,
    }
    if api_key:
        scan_headers["x-api-key"] = api_key

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(scan_url, json=scan_body, headers=scan_headers)

    data = resp.json()
    data["status_code"] = resp.status_code

    # Fail loudly on unexpected HTTP statuses (e.g. 404 from wrong URL)
    if resp.status_code not in (200, 403):
        raise RuntimeError(f"Unexpected proxy response {resp.status_code} from {scan_url}: {data}")

    return data


async def _demo_llm_call(state: AgentState, settings: Any) -> AgentState:
    """Demo mode: route through proxy for real firewall, mock for response.

    1. Send the user message to /v1/scan → runs the security pipeline
       (Presidio, LLM Guard, NeMo, custom rules) without an LLM call.
    2. If the scan returns BLOCK (403) → honour it and stop.
    3. If ALLOW → use mock_agent_llm for the agent response (tool calls
       etc.) but inject the **real** firewall decision.
    """
    from src.agent.mock_llm import mock_agent_llm

    messages = build_messages(state)
    session_id = state.get("session_id", "unknown")
    policy = state.get("policy", settings.default_policy)
    trace = TraceAccumulator(state.get("trace"))
    model_name = state.get("model", settings.default_model)
    start = time.perf_counter()

    firewall_decision: dict = {
        "decision": "ALLOW",
        "risk_score": 0.0,
        "intent": "",
        "risk_flags": {},
    }

    # Build scan-safe messages: chat history + current user message.
    # We strip the system prompt (anti-injection rules) and tool delimiters
    # because those trigger false-positives in the proxy's injection detector.
    chat_history = state.get("chat_history", [])
    user_msg = state.get("message", "")
    scan_messages = [*chat_history, {"role": "user", "content": user_msg}]

    try:
        scan_data = await _scan_via_proxy(
            proxy_base_url=settings.proxy_base_url,
            session_id=session_id,
            policy=policy,
            api_key=None,
            scan_messages=scan_messages,
            model_name=model_name,
            temperature=settings.default_temperature,
            max_tokens=settings.default_max_tokens,
        )

        if scan_data.get("status_code") == 403:
            # Firewall BLOCK — honour it
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            blocked_reason = scan_data.get("blocked_reason", "Request blocked by security policy.")

            firewall_decision = {
                "decision": "BLOCK",
                "risk_score": scan_data.get("risk_score", 1.0),
                "risk_flags": scan_data.get("risk_flags", {}),
                "intent": scan_data.get("intent", ""),
                "blocked_reason": blocked_reason,
            }

            trace.record_llm_call(
                messages_count=len(messages),
                duration_ms=elapsed_ms,
                firewall=firewall_decision,
            )

            return {
                **state,
                "llm_messages": messages,
                "llm_response": "",
                "firewall_decision": firewall_decision,
                "final_response": f"I'm sorry, but I can't process that request. {blocked_reason}",
                "trace": trace.data,
            }

        # ALLOW — extract firewall decision from scan response
        firewall_decision = {
            "decision": scan_data.get("decision", "ALLOW"),
            "risk_score": scan_data.get("risk_score", 0.0),
            "intent": scan_data.get("intent", ""),
            "risk_flags": scan_data.get("risk_flags", {}),
        }

    except Exception as e:
        # Non-fatal: if proxy unreachable, fall through with default ALLOW
        logger.warning("demo_proxy_unreachable", error=str(e))

    # ── Scan returned ALLOW/MODIFY → use mock for agent response ──
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    mock_state = mock_agent_llm(state)
    mock_state["firewall_decision"] = firewall_decision

    trace.record_llm_call(
        messages_count=len(messages),
        tokens_in=50,
        tokens_out=20,
        duration_ms=elapsed_ms,
        firewall=firewall_decision,
    )
    mock_state["trace"] = trace.data
    return mock_state


async def llm_call_node(state: AgentState) -> AgentState:
    """Call LLM with firewall scan + direct provider call (two-phase).

    Architecture:
      1. Send chat history + current user message to proxy for firewall scan
         (without the agent system prompt / tool delimiters which trigger
         false-positives).
      2. If BLOCK → honour it and stop.
      3. If ALLOW → call the LLM directly (bypassing proxy) with the full
         message set including system prompt, tool results & anti-injection
         delimiters so the model can use tool outputs in its answer.
    """
    settings = get_settings()

    api_key = state.get("api_key")

    # ── Demo mode: real firewall scan + mock agent response ──
    if not api_key and settings.mode == "demo":
        return await _demo_llm_call(state, settings)

    # ── Real provider (API key or real mode) ─────────────────

    # Silence LiteLLM logs
    os.environ.setdefault("LITELLM_LOG", settings.litellm_log_level)

    messages = build_messages(state)
    session_id = state.get("session_id", "unknown")
    policy = state.get("policy", settings.default_policy)
    trace = TraceAccumulator(state.get("trace"))

    firewall_decision: dict = {
        "decision": "UNKNOWN",
        "risk_score": 0.0,
        "intent": "",
        "risk_flags": {},
    }

    start = time.perf_counter()

    model_name = state.get("model", settings.default_model)

    # ── Step 1: Firewall scan via /v1/scan (no LLM call) ───────────
    # Send chat history + current user message (without the agent system
    # prompt / tool delimiters which trigger false-positives).  The proxy
    # only scans the *last* user message (parse_node) so history is safe.
    chat_history = state.get("chat_history", [])
    user_msg = state.get("message", "")
    scan_messages = [*chat_history, {"role": "user", "content": user_msg}]

    try:
        scan_data = await _scan_via_proxy(
            proxy_base_url=settings.proxy_base_url,
            session_id=session_id,
            policy=policy,
            api_key=api_key,
            scan_messages=scan_messages,
            model_name=model_name,
            temperature=settings.default_temperature,
            max_tokens=settings.default_max_tokens,
        )

        if scan_data.get("status_code") == 403:
            # Firewall BLOCK
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            blocked_reason = scan_data.get("blocked_reason", "Request blocked by security policy.")
            firewall_decision = {
                "decision": "BLOCK",
                "risk_score": scan_data.get("risk_score", 1.0),
                "risk_flags": scan_data.get("risk_flags", {}),
                "intent": scan_data.get("intent", ""),
                "blocked_reason": blocked_reason,
            }

            trace.record_llm_call(
                messages_count=len(messages),
                duration_ms=elapsed_ms,
                firewall=firewall_decision,
            )

            return {
                **state,
                "llm_messages": messages,
                "llm_response": "",
                "firewall_decision": firewall_decision,
                "final_response": f"I'm sorry, but I can't process that request. {blocked_reason}",
                "trace": trace.data,
            }

        # ALLOW — extract firewall decision from scan response
        firewall_decision = {
            "decision": scan_data.get("decision", "ALLOW"),
            "risk_score": scan_data.get("risk_score", 0.0),
            "intent": scan_data.get("intent", ""),
            "risk_flags": scan_data.get("risk_flags", {}),
        }

        # ── Step 2: Direct LLM call with full context ────────────────
        # The firewall scan passed (ALLOW).  Now call the LLM directly
        # with the complete message set including system prompt and tool
        # results so the model can actually use tool outputs in its answer.
        direct_model, direct_kwargs = _resolve_direct_llm(model_name, api_key, settings)

        full_resp = await acompletion(
            model=direct_model,
            messages=messages,  # full: system + history + user + tool results
            temperature=settings.default_temperature,
            max_tokens=settings.default_max_tokens,
            timeout=120,
            **direct_kwargs,
        )

        llm_text = full_resp.choices[0].message.content or ""

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info("llm_call_ok", elapsed_ms=elapsed_ms, response_len=len(llm_text))

        # ── Token tracking (spec 06) ─────────────────────
        token_state = _track_tokens(full_resp, state, model_name)

        # Trace (spec 07)
        usage = getattr(full_resp, "usage", None)
        trace.record_llm_call(
            messages_count=len(messages),
            tokens_in=int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0,
            tokens_out=int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0,
            duration_ms=elapsed_ms,
            firewall=firewall_decision,
        )

        return {
            **state,
            **token_state,
            "llm_messages": messages,
            "llm_response": llm_text,
            "firewall_decision": firewall_decision,
            "trace": trace.data,
        }

    except APIError as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.warning("llm_call_api_error", status=e.status_code, elapsed_ms=elapsed_ms)

        error_msg = f"LLM service error: {e}"
        return {
            **state,
            "llm_messages": messages,
            "llm_response": "",
            "firewall_decision": firewall_decision,
            "errors": [*state.get("errors", []), error_msg],
            "final_response": "I'm experiencing technical difficulties. Please try again.",
            "trace": trace.data,
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
            "trace": trace.data,
        }
