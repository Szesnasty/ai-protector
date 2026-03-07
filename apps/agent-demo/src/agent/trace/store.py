"""TraceStore — in-memory persistence for agent traces (spec 07 Phase 2).

Stores finalized traces in a bounded dict keyed by trace_id.
Supports filtering by session_id, user_role, decision, date range, and has_blocks.

Architecture note: this is an in-memory store (same pattern as SessionStore).
For production use, replace with a PostgreSQL/JSONB backend — the interface
is designed to make that swap transparent.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any

import structlog

logger = structlog.get_logger()

# Maximum stored traces (LRU eviction)
DEFAULT_MAX_TRACES = 10_000


class TraceStore:
    """Thread-safe in-memory trace store with LRU eviction and query filters."""

    def __init__(self, max_traces: int = DEFAULT_MAX_TRACES) -> None:
        self._max_traces = max_traces
        self._traces: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    # ── Write ─────────────────────────────────────────────

    def save(self, trace: dict[str, Any]) -> str:
        """Persist a finalized trace. Returns the trace_id."""
        trace_id = trace.get("trace_id", "")
        if not trace_id:
            logger.warning("trace_store_save_skip", reason="no trace_id")
            return ""

        with self._lock:
            # LRU eviction
            if len(self._traces) >= self._max_traces and trace_id not in self._traces:
                self._traces.popitem(last=False)

            self._traces[trace_id] = dict(trace)
            # Move to end (most recent)
            self._traces.move_to_end(trace_id)

        logger.info("trace_stored", trace_id=trace_id, session_id=trace.get("session_id"))
        return trace_id

    # ── Read ──────────────────────────────────────────────

    def get(self, trace_id: str) -> dict[str, Any] | None:
        """Get a single trace by ID."""
        with self._lock:
            return self._traces.get(trace_id)

    def list(
        self,
        *,
        session_id: str | None = None,
        user_role: str | None = None,
        has_blocks: bool | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Query traces with filters. Returns {items, total, limit, offset}."""
        with self._lock:
            candidates = list(reversed(self._traces.values()))  # newest first

        # Apply filters
        filtered = []
        for t in candidates:
            if session_id and t.get("session_id") != session_id:
                continue
            if user_role and t.get("user_role") != user_role:
                continue
            if has_blocks is not None:
                blocked_count = t.get("counters", {}).get("tool_calls_blocked", 0)
                has_fw_block = False
                for it in t.get("iterations", []):
                    fw = it.get("firewall_decision") or {}
                    if fw.get("decision") == "BLOCK":
                        has_fw_block = True
                        break
                trace_has_blocks = blocked_count > 0 or has_fw_block
                if has_blocks and not trace_has_blocks:
                    continue
                if not has_blocks and trace_has_blocks:
                    continue
            if date_from:
                ts = t.get("timestamp", "")
                if ts and ts < date_from:
                    continue
            if date_to:
                ts = t.get("timestamp", "")
                if ts and ts > date_to:
                    continue
            filtered.append(t)

        total = len(filtered)
        page = filtered[offset : offset + limit]

        # Return summaries (not full trace) for list endpoint
        items = [_summarize(t) for t in page]

        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def count(self) -> int:
        """Total number of stored traces."""
        with self._lock:
            return len(self._traces)

    def clear(self) -> None:
        """Remove all traces (for testing)."""
        with self._lock:
            self._traces.clear()


def _summarize(trace: dict[str, Any]) -> dict[str, Any]:
    """Create a lightweight summary of a trace for list responses."""
    counters = trace.get("counters", {})
    return {
        "trace_id": trace.get("trace_id", ""),
        "session_id": trace.get("session_id", ""),
        "timestamp": trace.get("timestamp", ""),
        "user_role": trace.get("user_role", ""),
        "intent": trace.get("intent", ""),
        "model": trace.get("model", ""),
        "total_duration_ms": trace.get("total_duration_ms", 0),
        "iterations_count": counters.get("iterations", 0),
        "tool_calls_count": counters.get("tool_calls", 0),
        "tool_calls_blocked": counters.get("tool_calls_blocked", 0),
        "tokens_in": counters.get("tokens_in", 0),
        "tokens_out": counters.get("tokens_out", 0),
        "has_errors": len(trace.get("errors", [])) > 0,
        "limits_hit": trace.get("limits_hit"),
    }


# ── Singleton ─────────────────────────────────────────────

_store: TraceStore | None = None


def get_trace_store() -> TraceStore:
    """Get or create the singleton TraceStore."""
    global _store
    if _store is None:
        _store = TraceStore()
    return _store
