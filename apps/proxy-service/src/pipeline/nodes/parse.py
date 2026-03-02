"""ParseNode — first node in the pipeline, extracts & normalises the request."""

from __future__ import annotations

import hashlib

import structlog

from src.pipeline.nodes import timed_node
from src.pipeline.state import PipelineState

logger = structlog.get_logger()


@timed_node("parse")
async def parse_node(state: PipelineState) -> PipelineState:
    """Extract and normalise incoming request into pipeline state fields.

    Always runs first.  Initialises all accumulator fields so downstream
    nodes can safely read them without ``KeyError``.
    """
    messages: list[dict] = state.get("messages", [])

    # Extract last user message
    user_message = ""
    found_user = False
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            found_user = True
            break

    errors: list[str] = []
    if not found_user:
        errors.append("parse: no user message found in conversation")
        logger.warning("parse_no_user_message", request_id=state.get("request_id"))

    prompt_hash = hashlib.sha256(user_message.encode()).hexdigest()

    return {
        **state,
        "user_message": user_message,
        "prompt_hash": prompt_hash,
        # Initialise accumulators
        "risk_flags": {},
        "risk_score": 0.0,
        "rules_matched": [],
        "scanner_results": {},
        "decision": None,
        "blocked_reason": None,
        "modified_messages": None,
        "errors": errors,
        "node_timings": {},
        "response_masked": False,
    }
