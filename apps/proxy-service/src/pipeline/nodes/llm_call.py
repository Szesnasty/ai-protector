"""LLMCallNode — wraps the existing LiteLLM client for non-streaming calls."""

from __future__ import annotations

from src.llm.client import llm_completion
from src.pipeline.nodes import timed_node
from src.pipeline.state import PipelineState


@timed_node("llm_call")
async def llm_call_node(state: PipelineState) -> PipelineState:
    """Call LLM via LiteLLM.  Uses ``modified_messages`` if available."""
    messages = state.get("modified_messages") or state["messages"]

    response = await llm_completion(
        messages=messages,
        model=state["model"],
        stream=False,  # streaming handled separately at router level
        temperature=state.get("temperature", 0.7),
        max_tokens=state.get("max_tokens"),
        api_key=state.get("api_key"),
        intent=state.get("intent", ""),
    )

    usage = getattr(response, "usage", None)
    return {
        **state,
        "llm_response": response,
        "tokens_in": getattr(usage, "prompt_tokens", None) if usage else None,
        "tokens_out": getattr(usage, "completion_tokens", None) if usage else None,
    }
