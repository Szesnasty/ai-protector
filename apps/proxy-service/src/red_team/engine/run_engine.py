"""Run Engine — orchestrates a full benchmark run.

Central coordinator: load pack → iterate scenarios → send prompts →
normalize → evaluate → collect results → compute scores → persist.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from src.red_team.engine.protocols import (
    HttpClientProtocol,
    NormalizerProtocol,
    PersistenceProtocol,
    ProgressEmitterProtocol,
)
from src.red_team.evaluators import evaluate_scenario
from src.red_team.packs import FilteredPack, TargetConfig, filter_pack, load_pack
from src.red_team.schemas import Scenario
from src.red_team.schemas.dataclasses import EvalResult
from src.red_team.scoring import ScenarioOutcome, ScenarioResult, ScoreResult, compute_scores

# ---------------------------------------------------------------------------
# Enums & config
# ---------------------------------------------------------------------------


class RunState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class RunConfig:
    """Configuration for a benchmark run."""

    target_type: str  # "demo" | "local_agent" | "hosted_endpoint"
    target_config: dict[str, Any]  # endpoint_url, agent_type, safe_mode, timeout_s, etc.
    pack: str  # "core_security" | "agent_threats"
    policy: str | None = None  # nullable for external targets
    source_run_id: str | None = None  # Set for re-runs
    idempotency_key: str | None = None  # Client-generated, prevents double-click


# ---------------------------------------------------------------------------
# Run record (in-memory representation)
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkRun:
    """In-memory representation of a benchmark run."""

    id: str
    config: RunConfig
    state: RunState
    target_fingerprint: str
    filtered_pack: FilteredPack
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    results: list[ScenarioResult] = field(default_factory=list)
    eval_results: list[tuple[str, EvalResult]] = field(default_factory=list)  # (scenario_id, eval_result)
    score: ScoreResult | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Target fingerprint
# ---------------------------------------------------------------------------


_FINGERPRINT_EXCLUDE_KEYS = frozenset({"auth_secret_ref", "auth_header"})


def compute_target_fingerprint(target_type: str, target_config: dict[str, Any]) -> str:
    """Compute a stable fingerprint from target_type + target_config.

    Auth-related fields are excluded so that re-encryptions with
    different nonces produce the same fingerprint for the same target.
    """
    safe_config = {k: v for k, v in target_config.items() if k not in _FINGERPRINT_EXCLUDE_KEYS}
    payload = json.dumps({"type": target_type, "config": safe_config}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Run Engine
# ---------------------------------------------------------------------------

_MAX_CONSECUTIVE_FAILURES = 3
_RETRY_DELAY_S = 2.0
_DEFAULT_TIMEOUT_S = 30.0
_IDEMPOTENCY_WINDOW_S = 60.0


class RunEngine:
    """Orchestrates benchmark run lifecycle."""

    def __init__(
        self,
        http_client: HttpClientProtocol,
        normalizer: NormalizerProtocol,
        persistence: PersistenceProtocol,
        progress: ProgressEmitterProtocol,
    ) -> None:
        self._http = http_client
        self._normalizer = normalizer
        self._persistence = persistence
        self._progress = progress

    # -------------------------------------------------------------------
    # Create
    # -------------------------------------------------------------------

    async def create_run(self, config: RunConfig) -> BenchmarkRun:
        """Create a new benchmark run.

        - Validates config
        - Checks idempotency key
        - Checks concurrency guard
        - Loads and filters pack
        - Persists run record
        """
        self._validate_config(config)

        # Idempotency check
        if config.idempotency_key:
            existing = await self._persistence.find_by_idempotency_key(config.idempotency_key)
            if existing:
                return self._run_from_record(existing)

        # Compute fingerprint
        fingerprint = compute_target_fingerprint(config.target_type, config.target_config)

        # Concurrency guard
        active = await self._persistence.find_active_run(fingerprint)
        if active:
            raise ConcurrencyConflictError(
                f"Run already active for target fingerprint {fingerprint}: {active.get('id', 'unknown')}"
            )

        # Load and filter pack
        agent_type = config.target_config.get("agent_type", "chatbot_api")
        safe_mode = config.target_config.get("safe_mode", False)
        pack = load_pack(config.pack)
        target_cfg = TargetConfig(agent_type=agent_type, safe_mode=safe_mode)
        filtered = filter_pack(pack, target_cfg)

        # Create run
        run_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        run = BenchmarkRun(
            id=run_id,
            config=config,
            state=RunState.CREATED,
            target_fingerprint=fingerprint,
            filtered_pack=filtered,
            created_at=now,
        )

        # Persist
        await self._persistence.create_run(
            {
                "id": run_id,
                "config": {
                    "target_type": config.target_type,
                    "target_config": config.target_config,
                    "pack": config.pack,
                    "policy": config.policy,
                    "source_run_id": config.source_run_id,
                    "idempotency_key": config.idempotency_key,
                },
                "state": RunState.CREATED.value,
                "target_fingerprint": fingerprint,
                "total_in_pack": filtered.total_in_pack,
                "total_applicable": filtered.total_applicable,
                "skipped_count": filtered.skipped_count,
                "skipped_reasons": filtered.skipped_reasons,
                "created_at": now.isoformat(),
            }
        )

        return run

    # -------------------------------------------------------------------
    # Execute
    # -------------------------------------------------------------------

    async def execute_run(self, run: BenchmarkRun) -> BenchmarkRun:
        """Execute all scenarios in a run.

        This is the worker entry point — called asynchronously.
        """
        # Transition to running
        run.state = RunState.RUNNING
        run.started_at = datetime.now(UTC)
        await self._persistence.update_run(
            run.id,
            {
                "state": RunState.RUNNING.value,
                "started_at": run.started_at.isoformat(),
            },
        )

        consecutive_failures = 0
        scenarios = run.filtered_pack.scenarios
        total = len(scenarios)

        for i, scenario in enumerate(scenarios):
            # Check for cancellation
            if run.state == RunState.CANCELLED:
                break

            await self._progress.emit(
                run.id,
                {
                    "type": "scenario_start",
                    "scenario_id": scenario.id,
                    "scenario_title": scenario.title,
                    "index": i,
                    "total": total,
                },
            )

            try:
                result = await self._execute_scenario(run, scenario)
                consecutive_failures = 0

                run.results.append(result)
                run.eval_results.append((scenario.id, result))

                await self._persistence.persist_result(
                    run.id,
                    {
                        "scenario_id": scenario.id,
                        "outcome": result.outcome.value,
                        "severity": result.severity,
                        "category": result.category,
                        "confidence": result.confidence,
                    },
                )

                await self._progress.emit(
                    run.id,
                    {
                        "type": "scenario_complete",
                        "scenario_id": scenario.id,
                        "outcome": result.outcome.value,
                        "index": i,
                        "total": total,
                    },
                )

            except ConnectionError:
                consecutive_failures += 1
                skip_result = ScenarioResult(
                    scenario_id=scenario.id,
                    category=scenario.category.value if hasattr(scenario.category, "value") else str(scenario.category),
                    severity=scenario.severity.value if hasattr(scenario.severity, "value") else str(scenario.severity),
                    outcome=ScenarioOutcome.SKIPPED,
                    skip_reason="connection_error",
                )
                run.results.append(skip_result)

                await self._progress.emit(
                    run.id,
                    {
                        "type": "scenario_skipped",
                        "scenario_id": scenario.id,
                        "reason": "connection_error",
                    },
                )

                if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                    run.state = RunState.FAILED
                    run.error = f"Run failed: {consecutive_failures} consecutive connection failures"
                    run.completed_at = datetime.now(UTC)
                    await self._persistence.update_run(
                        run.id,
                        {
                            "state": RunState.FAILED.value,
                            "error": run.error,
                            "completed_at": run.completed_at.isoformat(),
                        },
                    )
                    await self._progress.emit(
                        run.id,
                        {
                            "type": "run_failed",
                            "error": run.error,
                        },
                    )
                    return run

            except TimeoutError:
                skip_result = ScenarioResult(
                    scenario_id=scenario.id,
                    category=scenario.category.value if hasattr(scenario.category, "value") else str(scenario.category),
                    severity=scenario.severity.value if hasattr(scenario.severity, "value") else str(scenario.severity),
                    outcome=ScenarioOutcome.SKIPPED,
                    skip_reason="timeout",
                )
                run.results.append(skip_result)
                consecutive_failures = 0  # Timeout is not a connection failure

                await self._progress.emit(
                    run.id,
                    {
                        "type": "scenario_skipped",
                        "scenario_id": scenario.id,
                        "reason": "timeout",
                    },
                )

        # Compute scores and finalize
        if run.state != RunState.CANCELLED and run.state != RunState.FAILED:
            run.score = compute_scores(
                run.results,
                total_in_pack=run.filtered_pack.total_in_pack,
                skipped_reasons=run.filtered_pack.skipped_reasons,
            )
            run.state = RunState.COMPLETED
            run.completed_at = datetime.now(UTC)

            await self._persistence.update_run(
                run.id,
                {
                    "state": RunState.COMPLETED.value,
                    "score_simple": run.score.score_simple,
                    "score_weighted": run.score.score_weighted,
                    "completed_at": run.completed_at.isoformat(),
                },
            )

            await self._progress.emit(
                run.id,
                {
                    "type": "run_complete",
                    "score_simple": run.score.score_simple,
                    "score_weighted": run.score.score_weighted,
                },
            )

        return run

    # -------------------------------------------------------------------
    # Cancel
    # -------------------------------------------------------------------

    async def cancel_run(self, run: BenchmarkRun) -> BenchmarkRun:
        """Cancel a running run."""
        if run.state != RunState.RUNNING:
            raise InvalidStateError(f"Cannot cancel run in state {run.state.value}")

        run.state = RunState.CANCELLED
        run.completed_at = datetime.now(UTC)

        # Compute partial scores
        if run.results:
            run.score = compute_scores(
                run.results,
                total_in_pack=run.filtered_pack.total_in_pack,
                skipped_reasons=run.filtered_pack.skipped_reasons,
            )

        await self._persistence.update_run(
            run.id,
            {
                "state": RunState.CANCELLED.value,
                "completed_at": run.completed_at.isoformat(),
            },
        )

        await self._progress.emit(run.id, {"type": "run_cancelled"})
        return run

    # -------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------

    async def _execute_scenario(self, run: BenchmarkRun, scenario: Scenario) -> ScenarioResult:
        """Execute a single scenario: send → normalize → evaluate."""
        timeout_s = run.config.target_config.get("timeout_s", _DEFAULT_TIMEOUT_S)

        try:
            http_response = await asyncio.wait_for(
                self._http.send_prompt(scenario.prompt, run.config.target_config),
                timeout=timeout_s,
            )
        except TimeoutError:
            raise TimeoutError(f"Scenario {scenario.id} timed out after {timeout_s}s") from None
        except ConnectionError:
            # Retry once
            try:
                await asyncio.sleep(_RETRY_DELAY_S)
                http_response = await asyncio.wait_for(
                    self._http.send_prompt(scenario.prompt, run.config.target_config),
                    timeout=timeout_s,
                )
            except (TimeoutError, ConnectionError) as exc:
                raise ConnectionError(f"Scenario {scenario.id} connection failed after retry") from exc

        # Normalize
        normalized = self._normalizer.normalize(http_response, run.config.target_config)

        # Evaluate
        eval_result = evaluate_scenario(scenario, normalized)

        # Convert to ScenarioResult
        category = scenario.category.value if hasattr(scenario.category, "value") else str(scenario.category)
        severity = scenario.severity.value if hasattr(scenario.severity, "value") else str(scenario.severity)

        if eval_result.passed:
            outcome = ScenarioOutcome.PASSED
        else:
            outcome = ScenarioOutcome.FAILED

        return ScenarioResult(
            scenario_id=scenario.id,
            category=category,
            severity=severity,
            outcome=outcome,
            confidence=eval_result.confidence,
        )

    def _validate_config(self, config: RunConfig) -> None:
        """Validate RunConfig fields."""
        if not config.target_type:
            raise ConfigValidationError("target_type is required")
        if not config.target_config:
            raise ConfigValidationError("target_config is required")
        if not config.pack:
            raise ConfigValidationError("pack name is required")

    def _run_from_record(self, record: dict[str, Any]) -> BenchmarkRun:
        """Reconstruct a BenchmarkRun from a persistence record."""
        config_data = record.get("config", {})
        config = RunConfig(
            target_type=config_data.get("target_type", ""),
            target_config=config_data.get("target_config", {}),
            pack=config_data.get("pack", ""),
            policy=config_data.get("policy"),
            source_run_id=config_data.get("source_run_id"),
            idempotency_key=config_data.get("idempotency_key"),
        )

        # Load pack to reconstruct filtered_pack
        agent_type = config.target_config.get("agent_type", "chatbot_api")
        safe_mode = config.target_config.get("safe_mode", False)
        pack = load_pack(config.pack)
        target_cfg = TargetConfig(agent_type=agent_type, safe_mode=safe_mode)
        filtered = filter_pack(pack, target_cfg)

        return BenchmarkRun(
            id=record["id"],
            config=config,
            state=RunState(record.get("state", "created")),
            target_fingerprint=record.get("target_fingerprint", ""),
            filtered_pack=filtered,
            created_at=datetime.fromisoformat(record["created_at"]) if "created_at" in record else datetime.now(UTC),
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ConfigValidationError(Exception):
    """Raised when RunConfig validation fails."""


class ConcurrencyConflictError(Exception):
    """Raised when a run is already active for the same target."""


class InvalidStateError(Exception):
    """Raised when a state transition is invalid."""
