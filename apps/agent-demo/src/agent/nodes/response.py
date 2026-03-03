"""ResponseNode — build the final structured response."""

from __future__ import annotations

import structlog

from src.agent.state import AgentState

logger = structlog.get_logger()


def response_node(state: AgentState) -> AgentState:
    """Build the final response text from LLM output or error fallback."""
    # If final_response was already set (e.g. by BLOCK handler), keep it
    if state.get("final_response"):
        logger.info("response_node", source="pre-set", length=len(state["final_response"]))
        return state

    llm_response = state.get("llm_response", "")

    if llm_response:
        final = llm_response
    elif state.get("intent") == "greeting":
        final = "Hello! I'm the Customer Support Copilot. How can I help you today?"
    else:
        final = "I'm sorry, I wasn't able to process your request. Please try again."

    logger.info("response_node", source="llm" if llm_response else "fallback", length=len(final))

    return {
        **state,
        "final_response": final,
    }
