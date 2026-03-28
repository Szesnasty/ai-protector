"""Adapters bridging engine protocols to real implementations.

These classes satisfy the Protocol interfaces defined in ``protocols.py``
and delegate to real infrastructure: httpx for HTTP, SQLAlchemy ORM for
persistence, and the in-memory ``ProgressEmitter`` for SSE events.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx

from src.red_team.engine.protocols import HttpResponse
from src.red_team.net import rewrite_localhost_for_docker
from src.red_team.progress.events import (
    RunCancelledEvent,
    RunCompleteEvent,
    RunFailedEvent,
    ScenarioCompleteEvent,
    ScenarioSkippedEvent,
    ScenarioStartEvent,
)
from src.red_team.schemas.dataclasses import RawTargetResponse

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.red_team.progress.emitter import ProgressEmitter

# ---------------------------------------------------------------------------
# Default endpoints
# ---------------------------------------------------------------------------

_DEMO_AGENT_URL = "http://agent-demo:8002/agent/chat"


# ---------------------------------------------------------------------------
# HTTP Client
# ---------------------------------------------------------------------------


class RealHttpClient:
    """Send prompts to target endpoints via httpx.

    For demo targets the chat payload includes ``role`` and ``session_id``
    required by the demo agent.
    """

    async def send_prompt(self, prompt: str, target_config: dict[str, Any]) -> HttpResponse:
        endpoint_url = rewrite_localhost_for_docker(
            target_config.get("endpoint_url") or _DEMO_AGENT_URL
        )
        timeout_s: int = target_config.get("timeout_s", 30)

        headers: dict[str, str] = {"Content-Type": "application/json"}
        # Apply custom headers (new format) or legacy single auth
        decrypted_headers: dict[str, str] | None = target_config.get("_decrypted_headers")
        if decrypted_headers:
            headers.update(decrypted_headers)
        elif auth_header := target_config.get("_decrypted_auth"):
            headers["Authorization"] = auth_header

        # Payload shape depends on target
        if "/agent/chat" in endpoint_url:
            payload: dict[str, Any] = {
                "message": prompt,
                "role": target_config.get("benchmark_role", "customer"),
                "session_id": f"benchmark-{uuid.uuid4().hex[:8]}",
            }
        else:
            # OpenAI-style messages array — the industry standard for chat APIs
            messages: list[dict[str, str]] = []
            system_prompt = target_config.get("_system_prompt")
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            payload = {"messages": messages}

        start = time.monotonic()
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    endpoint_url,
                    json=payload,
                    headers=headers,
                    timeout=timeout_s,
                )
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Target did not respond within {timeout_s}s") from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise ConnectionError(f"Cannot reach target at {endpoint_url}") from exc

        latency_ms = (time.monotonic() - start) * 1000

        return HttpResponse(
            status_code=resp.status_code,
            body=resp.text,
            headers={k.lower(): v for k, v in resp.headers.items()},
            latency_ms=latency_ms,
        )


class ProtectedHttpClient:
    """Wrap :class:`RealHttpClient` with the AI Protector firewall pipeline.

    Before forwarding each prompt to the target, runs it through the
    pre-LLM pipeline (intent → rules → scanners → decision).
    If the pipeline returns BLOCK the prompt never reaches the target.
    """

    def __init__(self, inner: RealHttpClient, policy: str = "balanced") -> None:
        self._inner = inner
        self._policy = policy

    async def send_prompt(self, prompt: str, target_config: dict[str, Any]) -> HttpResponse:
        from src.pipeline.runner import run_pre_llm_pipeline

        request_id = f"bench-{uuid.uuid4().hex[:12]}"
        messages = [{"role": "user", "content": prompt}]

        start = time.monotonic()
        result = await run_pre_llm_pipeline(
            request_id=request_id,
            client_id="benchmark",
            policy_name=self._policy,
            model="benchmark-target",
            messages=messages,
            temperature=0.0,
            max_tokens=1024,
            stream=False,
            api_key=None,
        )
        pipeline_ms = (time.monotonic() - start) * 1000

        if result.get("decision") == "BLOCK":
            body = json.dumps({
                "error": "blocked",
                "reason": result.get("blocked_reason", ""),
            })
            return HttpResponse(
                status_code=403,
                body=body,
                headers={
                    "content-type": "application/json",
                    "x-decision": "BLOCK",
                    "x-risk-score": str(result.get("risk_score", 0)),
                    "x-intent": result.get("intent", ""),
                },
                latency_ms=pipeline_ms,
            )

        # ALLOW / MODIFY — forward to the real target
        return await self._inner.send_prompt(prompt, target_config)


class SimpleNormalizer:
    """Parse HTTP response bodies into ``RawTargetResponse``."""

    def normalize(self, http_response: HttpResponse, target_config: dict[str, Any]) -> RawTargetResponse:
        body = http_response.body
        parsed_json = None
        body_text = body
        provider_format = "plain_text"

        try:
            parsed_json = json.loads(body)
            provider_format = "generic_json"

            if isinstance(parsed_json, dict):
                body_text = (
                    parsed_json.get("response")
                    or parsed_json.get("output_text")
                    or parsed_json.get("message")
                    or parsed_json.get("content")
                    or parsed_json.get("text")
                    or parsed_json.get("output")
                    or body
                )
        except (json.JSONDecodeError, ValueError):
            pass

        return RawTargetResponse(
            body_text=str(body_text),
            parsed_json=parsed_json,
            tool_calls=None,
            status_code=http_response.status_code,
            latency_ms=http_response.latency_ms,
            raw_body=body,
            provider_format=provider_format,
        )


# ---------------------------------------------------------------------------
# DB Persistence
# ---------------------------------------------------------------------------


class DbPersistenceAdapter:
    """Adapt :class:`PersistenceProtocol` to SQLAlchemy ORM repositories."""

    def __init__(self, session: AsyncSession) -> None:
        from src.red_team.persistence.models import BenchmarkScenarioResult
        from src.red_team.persistence.repository import (
            BenchmarkRunRepository,
            BenchmarkScenarioResultRepository,
        )

        self._session = session
        self._run_repo = BenchmarkRunRepository(session)
        self._result_repo = BenchmarkScenarioResultRepository(session)
        self._ScenarioResultModel = BenchmarkScenarioResult

    # -- PersistenceProtocol --

    async def create_run(self, run_data: dict[str, Any]) -> str:
        # Not used — run is created by the service layer before engine starts.
        return run_data["id"]

    async def update_run(self, run_id: str, updates: dict[str, Any]) -> None:
        run = await self._run_repo.get(uuid.UUID(run_id))
        if not run:
            return

        field_map = {"state": "status"}  # engine uses "state", ORM uses "status"
        for key, value in updates.items():
            attr = field_map.get(key, key)
            if attr in ("started_at", "completed_at") and isinstance(value, str):
                value = datetime.fromisoformat(value)
            if hasattr(run, attr):
                setattr(run, attr, value)

        await self._session.commit()

    @staticmethod
    def _derive_actual(expected: str, outcome_passed: bool) -> str:
        if outcome_passed:
            return expected  # Model did what was expected
        return "ALLOW" if expected == "BLOCK" else "BLOCK"

    async def persist_result(self, run_id: str, result_data: dict[str, Any]) -> None:
        run_uuid = uuid.UUID(run_id)

        result = self._ScenarioResultModel(
            run_id=run_uuid,
            scenario_id=result_data["scenario_id"],
            category=result_data.get("category", "unknown"),
            severity=result_data.get("severity", "medium"),
            prompt=result_data.get("prompt", ""),
            expected=result_data.get("expected", "BLOCK"),
            actual=self._derive_actual(
                result_data.get("expected", "BLOCK"),
                result_data.get("outcome") == "passed",
            ),
            passed=result_data.get("outcome") == "passed",
            skipped=result_data.get("outcome") == "skipped",
            skipped_reason=result_data.get("skip_reason"),
            latency_ms=int(result_data.get("latency_ms", 0)),
            raw_response_body=result_data.get("raw_response_body"),
            detector_type=result_data.get("detector_type"),
            detector_detail=result_data.get("detector_detail"),
        )
        self._session.add(result)

        # Update run counters
        run = await self._run_repo.get(run_uuid)
        if run:
            outcome = result_data.get("outcome", "")
            run.executed = (run.executed or 0) + 1
            if outcome == "passed":
                run.passed = (run.passed or 0) + 1
            elif outcome == "failed":
                run.failed = (run.failed or 0) + 1

        await self._session.commit()

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        run = await self._run_repo.get(uuid.UUID(run_id))
        if not run:
            return None
        # Strip sensitive fields even for internal engine reads (defence-in-depth)
        cfg = dict(run.target_config or {})
        cfg.pop("auth_secret_ref", None)
        cfg.pop("_decrypted_headers", None)
        cfg.pop("_decrypted_auth", None)
        return {
            "id": str(run.id),
            "config": {
                "target_type": run.target_type,
                "target_config": cfg,
                "pack": run.pack,
                "policy": run.policy,
            },
            "state": run.status,
            "target_fingerprint": run.target_fingerprint,
            "total_in_pack": run.total_in_pack,
            "total_applicable": run.total_applicable,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }

    async def find_active_run(self, target_fingerprint: str) -> dict[str, Any] | None:
        run = await self._run_repo.find_running_for_target(target_fingerprint)
        if not run:
            return None
        return {"id": str(run.id)}

    async def find_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        run = await self._run_repo.find_by_idempotency_key(uuid.UUID(key))
        if not run:
            return None
        return {"id": str(run.id)}


# ---------------------------------------------------------------------------
# Progress Bridge
# ---------------------------------------------------------------------------


class ProgressBridge:
    """Convert engine dict events → typed :class:`ProgressEvent` for SSE."""

    def __init__(self, emitter: ProgressEmitter) -> None:
        self._emitter = emitter

    async def emit(self, run_id: str, event: dict[str, Any]) -> None:
        run_uuid = uuid.UUID(run_id)
        typed = self._to_typed(event)
        if typed is not None:
            await self._emitter.emit(run_uuid, typed)

    @staticmethod
    def _to_typed(data: dict[str, Any]) -> Any | None:  # noqa: ANN401
        t = data.get("type", "")

        if t == "scenario_start":
            return ScenarioStartEvent(
                scenario_id=data["scenario_id"],
                index=data.get("index", 0),
                total_applicable=data.get("total", 0),
                title=data.get("title", "") or data.get("scenario_title", ""),
            )
        if t == "scenario_complete":
            passed = data.get("outcome") == "passed"
            return ScenarioCompleteEvent(
                scenario_id=data["scenario_id"],
                passed=passed,
                actual="BLOCK" if passed else "ALLOW",
                latency_ms=int(data.get("latency_ms", 0)),
                title=data.get("title", ""),
            )
        if t == "scenario_skipped":
            return ScenarioSkippedEvent(
                scenario_id=data["scenario_id"],
                reason=data.get("reason", "unknown"),
                title=data.get("title", ""),
            )
        if t == "run_complete":
            return RunCompleteEvent(
                score_simple=data.get("score_simple", 0),
                score_weighted=data.get("score_weighted", 0),
                total_in_pack=data.get("total_in_pack", 0),
                total_applicable=data.get("total_applicable", 0),
                executed=data.get("executed", 0),
                passed=data.get("passed", 0),
                failed=data.get("failed", 0),
                skipped=data.get("skipped", 0),
                skipped_reasons=data.get("skipped_reasons", {}),
            )
        if t == "run_failed":
            return RunFailedEvent(
                error=data.get("error", "Unknown error"),
                completed_scenarios=data.get("completed_scenarios", 0),
            )
        if t == "run_cancelled":
            return RunCancelledEvent(
                completed_scenarios=data.get("completed_scenarios", 0),
                partial_score=data.get("partial_score"),
            )
        return None
