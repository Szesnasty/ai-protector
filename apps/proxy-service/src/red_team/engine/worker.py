"""Background worker — launches benchmark engine execution.

Called from the API route via ``asyncio.create_task``.
Creates a fresh DB session, constructs the engine with real adapters,
reconstructs the in-memory run representation, and runs all scenarios.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.red_team.engine.adapters import (
    DbPersistenceAdapter,
    ProgressBridge,
    ProtectedHttpClient,
    RealHttpClient,
    SimpleNormalizer,
)
from src.red_team.engine.run_engine import BenchmarkRun, RunConfig, RunEngine, RunState
from src.red_team.packs import TargetConfig, filter_pack, load_pack

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.red_team.progress.emitter import ProgressEmitter


async def run_benchmark_background(
    run_id: uuid.UUID,
    emitter: ProgressEmitter,
) -> None:
    """Execute a benchmark run in the background.

    This function is safe to ``asyncio.create_task()``; it manages its own
    DB session and swallows all exceptions so the event loop is not affected.
    """
    from src.db.session import async_session

    try:
        async with async_session() as session:
            await _execute(session, run_id, emitter)
    except Exception:
        # Last-resort: mark the run as failed so the UI can react.
        try:
            async with async_session() as session:
                from src.red_team.persistence.repository import BenchmarkRunRepository

                repo = BenchmarkRunRepository(session)
                run = await repo.get(run_id)
                if run and run.status in ("created", "running"):
                    run.status = "failed"
                    run.error = "Unexpected engine error"
                    run.completed_at = datetime.now(UTC)
                    await session.commit()
        except Exception:
            pass


async def _execute(
    session: AsyncSession,  # noqa: F821 — deferred import
    run_id: uuid.UUID,
    emitter: ProgressEmitter,
) -> None:
    """Core execution logic."""
    from src.red_team.persistence.repository import BenchmarkRunRepository

    repo = BenchmarkRunRepository(session)
    run_orm = await repo.get(run_id)
    if not run_orm or run_orm.status != "created":
        return  # already started, cancelled, or missing

    # ── Decrypt auth if present ──────────────────────────────────────
    target_config = dict(run_orm.target_config or {})
    auth_ref = target_config.get("auth_secret_ref")
    if auth_ref:
        try:
            import json as _json

            from src.red_team.secrets.store import EncryptedColumnSecretStore

            store = EncryptedColumnSecretStore()
            raw = await store.retrieve(auth_ref)
            # New format: JSON dict of headers. Old format: plain string (Authorization value).
            try:
                parsed = _json.loads(raw)
                if isinstance(parsed, dict):
                    target_config["_decrypted_headers"] = parsed
                else:
                    target_config["_decrypted_headers"] = {"Authorization": raw}
            except (_json.JSONDecodeError, TypeError):
                target_config["_decrypted_headers"] = {"Authorization": raw}
        except Exception:
            logger.warning("Failed to decrypt auth for run %s — proceeding without auth", run_id)

    # ── Build engine ─────────────────────────────────────────────────
    persistence = DbPersistenceAdapter(session)
    progress = ProgressBridge(emitter)
    raw_client = RealHttpClient()

    # When through_proxy is set, wrap with the firewall pipeline
    if target_config.get("through_proxy"):
        policy = run_orm.policy or "balanced"
        http_client = ProtectedHttpClient(raw_client, policy=policy)
    else:
        http_client = raw_client

    normalizer = SimpleNormalizer()

    engine = RunEngine(
        http_client=http_client,
        normalizer=normalizer,
        persistence=persistence,
        progress=progress,
    )

    # ── Reconstruct in-memory BenchmarkRun ───────────────────────────
    config = RunConfig(
        target_type=run_orm.target_type,
        target_config=target_config,
        pack=run_orm.pack,
        policy=run_orm.policy,
        source_run_id=str(run_orm.source_run_id) if run_orm.source_run_id else None,
        idempotency_key=str(run_orm.idempotency_key) if run_orm.idempotency_key else None,
    )

    agent_type = target_config.get("agent_type", "chatbot_api")
    safe_mode = target_config.get("safe_mode", False)
    pack = load_pack(run_orm.pack)
    target_cfg = TargetConfig(agent_type=agent_type, safe_mode=safe_mode)
    filtered = filter_pack(pack, target_cfg)

    in_memory_run = BenchmarkRun(
        id=str(run_id),
        config=config,
        state=RunState.CREATED,
        target_fingerprint=run_orm.target_fingerprint,
        filtered_pack=filtered,
        created_at=run_orm.created_at or datetime.now(UTC),
    )

    # ── Execute ──────────────────────────────────────────────────────
    await engine.execute_run(in_memory_run)
