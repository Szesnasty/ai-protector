"""LLMCallNode — wraps the existing LiteLLM client for non-streaming calls.

When ``HARM_ML_MODE=post_llm`` the harm guard runs **in parallel** with the
provider call: the LLM request and the harm check start together, and if the
guard flags the prompt the (cancelled) response is replaced with a BLOCK. This
keeps the pre-LLM pipeline at ~50 ms while still catching harmful requests — the
guard's latency is hidden behind the (slower) provider call. Trade-off: the
prompt does reach the provider; the harmful *response* never reaches the user.
For block-before-provider semantics use ``HARM_ML_MODE=pre_llm`` instead.
"""

from __future__ import annotations

import asyncio
import contextlib

import structlog

from src.config import get_settings
from src.llm.client import llm_completion
from src.pipeline.nodes import timed_node
from src.pipeline.state import PipelineState

logger = structlog.get_logger()


@timed_node("llm_call")
async def llm_call_node(state: PipelineState) -> PipelineState:
    """Call LLM via LiteLLM.  Uses ``modified_messages`` if available."""
    messages = state.get("modified_messages") or state["messages"]
    settings = get_settings()

    async def _call():
        return await llm_completion(
            messages=messages,
            model=state["model"],
            stream=False,  # streaming handled separately at router level
            temperature=state.get("temperature", 0.7),
            max_tokens=state.get("max_tokens"),
            api_key=state.get("api_key"),
            intent=state.get("intent", ""),
        )

    # ── post_llm harm enforcement: run the guard concurrently with the call ──
    if settings.harm_ml_mode == "post_llm":
        from src.pipeline.nodes.harm_ml import check_harm

        text = state.get("scan_text") or state.get("user_message", "")
        llm_task = asyncio.create_task(_call())
        try:
            prob, flagged = await check_harm(text)
        except Exception as exc:  # noqa: BLE001
            prob, flagged = 0.0, False
            logger.error("harm_ml_post_error", error_type=type(exc).__name__)

        if flagged:
            llm_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await llm_task
            logger.warning("harm_ml_post_block", harm_probability=round(prob, 4), request_id=state.get("request_id"))
            return {
                **state,
                "decision": "BLOCK",
                "blocked_reason": f"Harmful request blocked post-LLM (P={prob:.2f})",
                "llm_response": None,
                "risk_flags": {**state.get("risk_flags", {}), "harm_ml": round(prob, 4)},
                "scanner_results": {
                    **state.get("scanner_results", {}),
                    "harm_ml": {"harm_probability": round(prob, 4)},
                },
            }
        response = await llm_task
    else:
        response = await _call()

    usage = getattr(response, "usage", None)
    return {
        **state,
        "llm_response": response,
        "tokens_in": getattr(usage, "prompt_tokens", None) if usage else None,
        "tokens_out": getattr(usage, "completion_tokens", None) if usage else None,
    }
