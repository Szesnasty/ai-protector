"""TraceAccumulator — builds structured agent trace incrementally.

Spec: docs/archive/agents/07-agents-trace/SPEC.md (Phase 1 — in-memory)

Each agent request creates a TraceAccumulator that every node contributes to.
The accumulator wraps a plain dict so it can be stored in AgentState and
serialized to JSON at the end.
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

_SECRET_RE = [
    re.compile(r"(?:sk|pk)-[a-zA-Z0-9]{20,}"),
    re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}"),
    re.compile(r"(?:Bearer|token)\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
    re.compile(r"(?:password|passwd|pwd)\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"AIzaSy[A-Za-z0-9_-]{33}"),
    re.compile(r"(?:api[_-]?key)\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"postgresql\+?\w*://\S+", re.IGNORECASE),
    re.compile(r"sk_live_\w+"),
]


def _redact(text: str) -> str:
    for p in _SECRET_RE:
        text = p.sub("[REDACTED]", text)
    return text


class TraceAccumulator:
    """Builds a structured agent trace dict incrementally.

    Usage::

        trace = TraceAccumulator()
        trace.start(session_id="s1", ...)
        trace.record_intent("order_query", 0.95)
        trace.start_iteration()
        trace.record_tool_plan([{"tool": "getOrderStatus", "args": {...}}])
        ...
        trace.finalize(final_response="Here is your order.", errors=[])
        result = trace.to_dict()
    """

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        if data is not None:
            self._trace = data
        else:
            self._trace: dict[str, Any] = {}
        # Restore internal bookkeeping from existing dict
        iterations = self._trace.get("iterations", [])
        self._iteration_count: int = len(iterations)
        self._current_iteration: dict[str, Any] | None = iterations[-1] if iterations else None
        self._start_time: float | None = self._trace.get("_perf_start")

    # ── Lifecycle ─────────────────────────────────────────

    def start(
        self,
        *,
        session_id: str,
        request_id: str = "",
        user_role: str = "customer",
        policy: str = "",
        model: str = "",
        user_message: str = "",
    ) -> None:
        """Initialize the trace at the beginning of a request."""
        self._start_time = time.perf_counter()
        self._iteration_count = 0
        self._current_iteration = None
        self._trace.update(
            {
                "_perf_start": self._start_time,
                "trace_id": str(uuid4()),
                "session_id": session_id,
                "request_id": request_id or str(uuid4()),
                "timestamp": datetime.now(UTC).isoformat(),
                "user_role": user_role,
                "policy": policy,
                "model": model,
                "user_message": _redact(user_message),
                "intent": None,
                "intent_confidence": 0.0,
                "iterations": [],
                "final_response": None,
                "total_duration_ms": 0,
                "node_timings": {},
                "counters": {
                    "iterations": 0,
                    "tool_calls": 0,
                    "tool_calls_blocked": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "estimated_cost": 0.0,
                },
                "limits_hit": None,
                "errors": [],
            }
        )

    # ── Intent ────────────────────────────────────────────

    def record_intent(self, intent: str, confidence: float) -> None:
        self._trace["intent"] = intent
        self._trace["intent_confidence"] = confidence

    # ── Iteration management ──────────────────────────────

    def start_iteration(self) -> None:
        """Begin a new agent loop iteration."""
        self._iteration_count += 1
        self._current_iteration = {
            "iteration": self._iteration_count,
            "tool_plan": [],
            "pre_tool_decisions": [],
            "tool_executions": [],
            "post_tool_decisions": [],
            "llm_call": None,
            "firewall_decision": None,
        }
        self._trace.setdefault("iterations", []).append(self._current_iteration)

    def _ensure_iteration(self) -> dict[str, Any]:
        if self._current_iteration is None:
            self.start_iteration()
        return self._current_iteration  # type: ignore[return-value]

    # ── Tool plan ─────────────────────────────────────────

    def record_tool_plan(self, plans: list[dict[str, Any]]) -> None:
        it = self._ensure_iteration()
        it["tool_plan"] = [{"tool": p.get("tool", ""), "args": p.get("args", {})} for p in plans]

    # ── Pre-tool gate ─────────────────────────────────────

    def record_pre_tool_decision(
        self,
        tool: str,
        decision: str,
        reason: str | None,
        checks: list[dict[str, Any]],
        risk_score: float = 0.0,
    ) -> None:
        it = self._ensure_iteration()
        it["pre_tool_decisions"].append(
            {
                "tool": tool,
                "decision": decision,
                "reason": reason,
                "checks": [dict(c) for c in checks],
                "risk_score": risk_score,
            }
        )
        if decision == "BLOCK":
            self._trace.setdefault("counters", {})["tool_calls_blocked"] = (
                self._trace.get("counters", {}).get("tool_calls_blocked", 0) + 1
            )

    # ── Tool execution ────────────────────────────────────

    def record_tool_execution(
        self,
        tool: str,
        args: dict[str, Any],
        result: str,
        duration_ms: int = 0,
    ) -> None:
        it = self._ensure_iteration()
        preview = _redact(result[:200]) if result else ""
        it["tool_executions"].append(
            {
                "tool": tool,
                "args": args,
                "result_preview": preview,
                "result_length": len(result) if result else 0,
                "duration_ms": duration_ms,
            }
        )
        self._trace.setdefault("counters", {})["tool_calls"] = self._trace.get("counters", {}).get("tool_calls", 0) + 1

    # ── Post-tool gate ────────────────────────────────────

    def record_post_tool_decision(
        self,
        tool: str,
        decision: str,
        pii_count: int = 0,
        secrets_count: int = 0,
        injection_score: float = 0.0,
        reason: str | None = None,
    ) -> None:
        it = self._ensure_iteration()
        it["post_tool_decisions"].append(
            {
                "tool": tool,
                "decision": decision,
                "pii_count": pii_count,
                "secrets_count": secrets_count,
                "injection_score": injection_score,
                "reason": reason,
            }
        )

    # ── LLM call ──────────────────────────────────────────

    def record_llm_call(
        self,
        messages_count: int = 0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        duration_ms: int = 0,
        firewall: dict[str, Any] | None = None,
    ) -> None:
        it = self._ensure_iteration()
        it["llm_call"] = {
            "messages_count": messages_count,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "duration_ms": duration_ms,
        }
        it["firewall_decision"] = firewall
        counters = self._trace.setdefault("counters", {})
        counters["tokens_in"] = counters.get("tokens_in", 0) + tokens_in
        counters["tokens_out"] = counters.get("tokens_out", 0) + tokens_out

    # ── Limits ────────────────────────────────────────────

    def record_limit_hit(self, limit_type: str) -> None:
        self._trace["limits_hit"] = limit_type

    # ── Node timings ──────────────────────────────────────

    def record_node_timing(self, node_name: str, duration_ms: float) -> None:
        self._trace.setdefault("node_timings", {})[node_name] = duration_ms

    # ── Finalize ──────────────────────────────────────────

    def finalize(
        self,
        final_response: str = "",
        errors: list[str] | None = None,
        node_timings: dict[str, float] | None = None,
        counters_override: dict[str, Any] | None = None,
    ) -> None:
        """Finalize the trace at the end of the request."""
        self._trace["final_response"] = _redact(final_response)
        if errors:
            self._trace["errors"] = errors
        if node_timings:
            self._trace["node_timings"] = node_timings
        if counters_override:
            self._trace.setdefault("counters", {}).update(counters_override)
        self._trace.setdefault("counters", {})["iterations"] = self._iteration_count
        if self._start_time is not None:
            self._trace["total_duration_ms"] = int((time.perf_counter() - self._start_time) * 1000)

    # ── Serialization ─────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Return the trace as a plain dict (without internal bookkeeping)."""
        d = dict(self._trace)
        d.pop("_perf_start", None)
        return d

    @property
    def data(self) -> dict[str, Any]:
        """Direct reference to the internal trace dict."""
        return self._trace
