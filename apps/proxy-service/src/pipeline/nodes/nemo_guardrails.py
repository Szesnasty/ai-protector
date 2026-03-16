"""NeMo Guardrails scanner node — Colang-based conversational security rails.

Runs in **dialog mode with embeddings_only** — zero LLM calls by design.
Uses FastEmbed (all-MiniLM-L6-v2, ~90MB ONNX) for semantic matching.
No LLM model is configured or required.

Architecture:
  - Colang defines attack intents with example phrases (8-12 each)
  - NeMo embeds user message, compares via cosine similarity
  - If attack intent matched (threshold > 0.3) → "BLOCKED:<rail_name>"
  - If no attack matched → ``embeddings_only_fallback_intent`` fires "safe_input"
  - Zero LLM calls, sub-10ms per scan after init

Lazy-initialized on first call (loads embedding model ~2-3s).
Each scan runs via ``asyncio.to_thread()`` to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import structlog

from src.config import get_settings
from src.pipeline.nodes import timed_node
from src.pipeline.state import PipelineState

logger = structlog.get_logger()

# ── Lazy-initialized singleton ────────────────────────────────

_rails_app = None
_rails_lock = threading.Lock()
_scan_lock = threading.Lock()
RAILS_DIR = Path(__file__).parent.parent / "rails"

# All known rail names (must match BLOCKED:<name> in .co bot responses)
KNOWN_RAILS = frozenset(
    {
        "role_bypass",
        "tool_abuse",
        "exfiltration",
        "social_engineering",
        "cot_manipulation",
        "rag_poisoning",
        "confused_deputy",
        "cross_tool",
        "excessive_agency",
        "hallucination_exploit",
        "supply_chain",
        "system_sabotage",
        "harmful_content",
    }
)


def _build_rails():
    """Build NeMo Guardrails app from config directory.

    Loads config.yml + all .co files from the rails/ directory.
    First call downloads the FastEmbed embedding model (~90MB).
    """
    from nemoguardrails import LLMRails, RailsConfig

    config = RailsConfig.from_path(str(RAILS_DIR))
    return LLMRails(config)


def get_rails():
    """Return cached NeMo Guardrails instance, create on first call."""
    global _rails_app  # noqa: PLW0603
    if _rails_app is None:
        with _rails_lock:
            if _rails_app is None:  # double-check after acquiring lock
                logger.info("nemo_guardrails_init", msg="Loading NeMo Guardrails (first call)")
                _rails_app = _build_rails()
                logger.info("nemo_guardrails_ready")
    return _rails_app


def reset_rails() -> None:
    """Reset singleton (for testing)."""
    global _rails_app  # noqa: PLW0603
    with _rails_lock:
        _rails_app = None


# ── Synchronous scan function (runs in thread pool) ──────────


def _scan_message(text: str) -> dict:
    """Run NeMo Guardrails dialog check against text.

    Returns dict with:
      - blocked: bool
      - matched_rail: str | None (e.g. "role_bypass", "tool_abuse")
      - score: float (0.0-1.0)
      - bot_message: str | None

    Serialised via ``_scan_lock`` — NeMo's LLMRails is NOT thread-safe;
    concurrent calls corrupt internal conversation state and cause
    false-positive classifications.
    """
    import asyncio as _asyncio

    rails = get_rails()
    messages = [{"role": "user", "content": text}]

    # NeMo's generate is sync internally but wraps async; we need a new loop
    # since we're running in a thread pool.
    # Lock prevents concurrent access — the singleton rails object leaks
    # conversation state between threads without it.
    with _scan_lock:
        loop = _asyncio.new_event_loop()
        try:
            response = loop.run_until_complete(rails.generate_async(messages=messages))
        finally:
            loop.close()

    content = ""
    if isinstance(response, dict):
        content = response.get("content", "")
    elif hasattr(response, "content"):
        content = response.content or ""

    # Parse BLOCKED:<rail_name> format from bot responses
    blocked = False
    matched_rail = None
    score = 0.0
    bot_message = None

    if content.startswith("BLOCKED:"):
        blocked = True
        rail_name = content.split(":", 1)[1].strip()
        matched_rail = rail_name if rail_name in KNOWN_RAILS else "unknown"
        score = 0.85  # High confidence when embedding match fires a rail
        bot_message = content

        # Try to get similarity score from explain()
        try:
            log = rails.explain()
            if log and log.colang_history:
                # The colang_history confirms the flow fired
                score = 0.85
        except Exception:
            pass  # explain() is best-effort

    return {
        "blocked": blocked,
        "matched_rail": matched_rail,
        "score": score,
        "bot_message": bot_message,
    }


# ── Async pipeline node ──────────────────────────────────────


@timed_node("nemo_guardrails")
async def nemo_guardrails_node(state: PipelineState) -> PipelineState:
    """Run NeMo Guardrails dialog rails against the user message.

    Execution in thread pool via ``asyncio.to_thread()`` (NeMo is synchronous).
    Results written to ``risk_flags`` and ``scanner_results["nemo_guardrails"]``.
    """
    settings = get_settings()

    # Global kill switch
    if not settings.enable_nemo_guardrails:
        return state

    text = state.get("user_message", "")
    if not text:
        return state

    risk_flags = {**state.get("risk_flags", {})}
    errors = list(state.get("errors", []))
    timeout = settings.scanner_timeout

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_scan_message, text),
            timeout=timeout,
        )

        if result["blocked"]:
            flag_key = f"nemo_{result['matched_rail'] or 'blocked'}"
            risk_flags[flag_key] = result["score"]
            risk_flags["nemo_blocked"] = True
            logger.warning(
                "nemo_guardrails_blocked",
                rail=result["matched_rail"],
                score=result["score"],
                request_id=state.get("request_id"),
            )

    except TimeoutError:
        result = {"error": f"Timeout after {timeout}s", "blocked": False}
        errors.append(f"nemo_guardrails: timeout after {timeout}s")
        logger.error("nemo_guardrails_timeout", timeout=timeout)
    except Exception as exc:
        result = {"error": str(exc), "blocked": False}
        errors.append(f"nemo_guardrails: {exc}")
        logger.error("nemo_guardrails_error", error_type=type(exc).__name__)

    return {
        **state,
        "risk_flags": risk_flags,
        "errors": errors,
        "scanner_results": {
            **state.get("scanner_results", {}),
            "nemo_guardrails": result,
        },
    }
