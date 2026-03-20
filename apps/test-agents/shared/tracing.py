"""TraceCollector — lightweight structured trace builder + HTTP flush.

Builds the same trace shape as agent-demo's TraceAccumulator,
then POSTs the result to proxy-service /v1/agents/{id}/traces/ingest.

Usage::

    tc = TraceCollector(proxy_url="http://proxy:8000", agent_id="uuid-here")
    tc.start(session_id="s1", user_role="admin")
    tc.start_iteration()
    tc.record_pre_tool("getOrders", "ALLOW", None, [])
    tc.record_tool_exec("getOrders", {"user_id": "1"}, '{"orders":[]}', 12)
    tc.record_post_tool("getOrders", "clean", [])
    tc.finalize("Here are your orders.")
    await tc.flush()  # POST to proxy-service
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
import structlog

logger = structlog.get_logger()

_SECRET_RE = [
    re.compile(r"(?:sk|pk)-[a-zA-Z0-9]{20,}"),
    re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}"),
    re.compile(r"(?:Bearer|token)\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
    re.compile(r"(?:password|passwd|pwd)\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"(?:api[_-]?key)\s*[=:]\s*\S+", re.IGNORECASE),
]


def _redact(text: str) -> str:
    for p in _SECRET_RE:
        text = p.sub("[REDACTED]", text)
    return text


class TraceCollector:
    """Builds a structured trace dict and flushes it to proxy-service."""

    def __init__(self, proxy_url: str, agent_id: str) -> None:
        self._proxy_url = proxy_url.rstrip("/")
        self._agent_id = agent_id
        self._trace: dict[str, Any] = {}
        self._start_time: float | None = None
        self._iteration_count: int = 0
        self._current_iteration: dict[str, Any] | None = None

    # ── Lifecycle ─────────────────────────────────────────

    def start(
        self,
        *,
        session_id: str = "default",
        user_role: str = "user",
        model: str = "",
        user_message: str = "",
        policy: str = "",
    ) -> None:
        self._start_time = time.perf_counter()
        self._iteration_count = 0
        self._current_iteration = None
        self._trace = {
            "trace_id": str(uuid4()),
            "session_id": session_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "user_role": user_role,
            "model": model,
            "user_message": _redact(user_message),
            "policy": policy,
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

    @property
    def trace_id(self) -> str:
        return self._trace.get("trace_id", "")

    # ── Intent ────────────────────────────────────────────

    def record_intent(self, intent: str, confidence: float = 0.0) -> None:
        self._trace["intent"] = intent
        self._trace["intent_confidence"] = confidence

    # ── Iteration management ──────────────────────────────

    def start_iteration(self) -> None:
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

    # ── Pre-tool gate ─────────────────────────────────────

    def record_pre_tool(
        self,
        tool: str,
        decision: str,
        reason: str | None,
        checks: list[dict[str, Any]] | None = None,
        risk_score: float = 0.0,
    ) -> None:
        it = self._ensure_iteration()
        it["pre_tool_decisions"].append(
            {
                "tool": tool,
                "decision": decision,
                "reason": reason,
                "checks": checks or [],
                "risk_score": risk_score,
            }
        )
        if decision == "BLOCK":
            self._trace["counters"]["tool_calls_blocked"] = (
                self._trace["counters"].get("tool_calls_blocked", 0) + 1
            )

    # ── Tool execution ────────────────────────────────────

    def record_tool_exec(
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
        self._trace["counters"]["tool_calls"] = (
            self._trace["counters"].get("tool_calls", 0) + 1
        )

    # ── Post-tool gate ────────────────────────────────────

    def record_post_tool(
        self,
        tool: str,
        decision: str,
        findings: list[dict[str, Any]] | None = None,
        pii_count: int = 0,
        injection_score: float = 0.0,
    ) -> None:
        it = self._ensure_iteration()
        it["post_tool_decisions"].append(
            {
                "tool": tool,
                "decision": decision,
                "findings": findings or [],
                "pii_count": pii_count,
                "injection_score": injection_score,
            }
        )

    # ── Firewall / LLM ───────────────────────────────────

    def record_firewall(
        self,
        decision: str,
        intent: str | None = None,
        risk_score: float = 0.0,
        reason: str | None = None,
    ) -> None:
        it = self._ensure_iteration()
        it["firewall_decision"] = {
            "decision": decision,
            "intent": intent,
            "risk_score": risk_score,
            "reason": reason,
        }

    def record_llm_call(
        self,
        tokens_in: int = 0,
        tokens_out: int = 0,
        duration_ms: int = 0,
        messages_count: int = 0,
    ) -> None:
        it = self._ensure_iteration()
        it["llm_call"] = {
            "messages_count": messages_count,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "duration_ms": duration_ms,
        }
        counters = self._trace["counters"]
        counters["tokens_in"] = counters.get("tokens_in", 0) + tokens_in
        counters["tokens_out"] = counters.get("tokens_out", 0) + tokens_out

    # ── Limits ────────────────────────────────────────────

    def record_limit_hit(self, limit_type: str) -> None:
        self._trace["limits_hit"] = limit_type

    # ── Finalize ──────────────────────────────────────────

    def finalize(
        self,
        final_response: str = "",
        errors: list[str] | None = None,
    ) -> None:
        self._trace["final_response"] = _redact(final_response)
        if errors:
            self._trace["errors"] = errors
        self._trace["counters"]["iterations"] = self._iteration_count
        if self._start_time is not None:
            self._trace["total_duration_ms"] = int(
                (time.perf_counter() - self._start_time) * 1000
            )

    # ── Serialize ─────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return dict(self._trace)

    # ── HTTP flush ────────────────────────────────────────

    async def flush(self) -> bool:
        """POST trace to proxy-service. Returns True on success.

        Fire-and-forget: logs warning on failure, never raises.
        """
        if not self._agent_id or not self._trace.get("trace_id"):
            logger.warning("trace_flush_skip", reason="no agent_id or trace_id")
            return False

        url = f"{self._proxy_url}/v1/agents/{self._agent_id}/traces/ingest"
        payload = self.to_dict()

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
            if resp.status_code == 201:
                logger.info(
                    "trace_flushed",
                    trace_id=payload["trace_id"],
                    agent_id=self._agent_id,
                )
                return True
            logger.warning(
                "trace_flush_failed",
                status=resp.status_code,
                body=resp.text[:200],
                trace_id=payload["trace_id"],
            )
        except Exception as exc:
            logger.warning(
                "trace_flush_error",
                error=str(exc)[:200],
                trace_id=payload.get("trace_id"),
            )
        return False
