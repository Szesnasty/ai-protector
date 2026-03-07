"""GET /agent/traces — trace query & export endpoints (spec 07 Phase 2+3)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from src.agent.trace.store import get_trace_store

router = APIRouter(tags=["traces"])


@router.get("/agent/traces")
async def list_traces(
    session_id: str | None = Query(default=None, description="Filter by session ID"),
    user_role: str | None = Query(default=None, description="Filter by user role"),
    has_blocks: bool | None = Query(default=None, description="Filter traces with/without blocks"),
    date_from: str | None = Query(default=None, description="ISO datetime lower bound"),
    date_to: str | None = Query(default=None, description="ISO datetime upper bound"),
    limit: int = Query(default=50, ge=1, le=200, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
) -> dict:
    """List agent traces with optional filters and pagination."""
    store = get_trace_store()
    return store.list(
        session_id=session_id,
        user_role=user_role,
        has_blocks=has_blocks,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.get("/agent/traces/{trace_id}")
async def get_trace(trace_id: str) -> dict:
    """Get full trace detail by trace_id."""
    store = get_trace_store()
    trace = store.get(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")
    return trace


@router.get("/agent/traces/{trace_id}/export")
async def export_trace(trace_id: str) -> dict:
    """Export trace as a self-contained JSON incident bundle (Phase 3).

    Returns a document suitable for offline incident analysis,
    with summary statistics pre-computed.
    """
    store = get_trace_store()
    trace = store.get(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")

    counters = trace.get("counters", {})

    # Count blocks across iterations
    blocks = counters.get("tool_calls_blocked", 0)
    redactions = 0
    for it in trace.get("iterations", []):
        for post in it.get("post_tool_decisions", []):
            if post.get("decision") == "REDACT":
                redactions += 1
        fw = it.get("firewall_decision") or {}
        if fw.get("decision") == "BLOCK":
            blocks += 1

    return {
        "trace_id": trace.get("trace_id"),
        "exported_at": datetime.now(UTC).isoformat(),
        "session_id": trace.get("session_id"),
        "user_role": trace.get("user_role"),
        "policy": trace.get("policy"),
        "model": trace.get("model"),
        "user_message": trace.get("user_message"),
        "intent": trace.get("intent"),
        "intent_confidence": trace.get("intent_confidence"),
        "iterations": trace.get("iterations", []),
        "final_response": trace.get("final_response"),
        "errors": trace.get("errors", []),
        "summary": {
            "blocks": blocks,
            "redactions": redactions,
            "tool_calls": counters.get("tool_calls", 0),
            "tokens_in": counters.get("tokens_in", 0),
            "tokens_out": counters.get("tokens_out", 0),
            "estimated_cost": counters.get("estimated_cost", 0.0),
            "total_duration_ms": trace.get("total_duration_ms", 0),
            "limits_hit": trace.get("limits_hit"),
        },
    }
