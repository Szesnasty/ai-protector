"""LLM Guard scanner node — runs 5 input scanners against user prompts.

Scanners:
- PromptInjection: injection / jailbreak attempts
- Toxicity: toxic, hateful, violent language
- Secrets: API keys, passwords, tokens
- BanSubstrings: dangerous substrings (system prompt markers)
- InvisibleText: zero-width Unicode characters

Scanners are lazy-initialized on first call (loads ML models ~500MB).
Each scanner runs via ``asyncio.to_thread()`` to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio

import structlog

from src.config import get_settings
from src.pipeline.nodes import timed_node
from src.pipeline.state import PipelineState

logger = structlog.get_logger()

# ── Lazy-initialized scanner singleton ────────────────────────────────

_scanners: list | None = None


def _build_scanners(thresholds: dict) -> list:
    """Construct scanners with policy-driven thresholds."""
    from llm_guard.input_scanners import (
        BanSubstrings,
        InvisibleText,
        PromptInjection,
        Secrets,
        Toxicity,
    )
    from llm_guard.input_scanners.prompt_injection import (
        MatchType as PIMatchType,
    )

    return [
        PromptInjection(
            threshold=thresholds.get("injection_threshold", 0.5),
            match_type=PIMatchType.FULL,
        ),
        Toxicity(threshold=thresholds.get("toxicity_threshold", 0.7)),
        Secrets(),
        BanSubstrings(
            substrings=["SYSTEM:", "```system", "<|im_start|>system"],
            match_type="str",
            case_sensitive=False,
        ),
        InvisibleText(),
    ]


def get_scanners(thresholds: dict) -> list:
    """Return the cached scanner list, creating it on first call."""
    global _scanners  # noqa: PLW0603
    if _scanners is None:
        logger.info("llm_guard_init", msg="Loading LLM Guard scanners (first call)")
        _scanners = _build_scanners(thresholds)
        logger.info("llm_guard_ready", scanner_count=len(_scanners))
    return _scanners


def reset_scanners() -> None:
    """Reset scanner singleton (for testing)."""
    global _scanners  # noqa: PLW0603
    _scanners = None


# ── Node ──────────────────────────────────────────────────────────────


@timed_node("llm_guard")
async def llm_guard_node(state: PipelineState) -> PipelineState:
    """Run LLM Guard scanners against the user message.

    Each scanner is executed in a thread pool via ``asyncio.to_thread()``.
    Results are written to ``risk_flags`` (failed scanners) and
    ``scanner_results["llm_guard"]``.
    """
    settings = get_settings()

    # Global kill switch
    if not settings.enable_llm_guard:
        return state

    text = state.get("user_message", "")
    if not text:
        return state

    thresholds = state.get("policy_config", {}).get("thresholds", {})
    scanners = get_scanners(thresholds)

    results: dict[str, dict] = {}
    risk_flags: dict = {**state.get("risk_flags", {})}
    errors: list[str] = list(state.get("errors", []))
    timeout = settings.scanner_timeout

    for scanner in scanners:
        scanner_name = type(scanner).__name__
        try:
            sanitized, is_valid, score = await asyncio.wait_for(
                asyncio.to_thread(scanner.scan, text),
                timeout=timeout,
            )
            results[scanner_name] = {
                "is_valid": is_valid,
                "score": round(score, 4),
            }
            if not is_valid:
                flag_key = scanner_name.lower()
                risk_flags[flag_key] = round(score, 4)
                logger.warning(
                    "llm_guard_flag",
                    scanner=scanner_name,
                    score=round(score, 4),
                    request_id=state.get("request_id"),
                )
        except TimeoutError:
            results[scanner_name] = {"error": f"Timeout after {timeout}s"}
            errors.append(f"llm_guard.{scanner_name}: timeout after {timeout}s")
            logger.error("llm_guard_timeout", scanner=scanner_name, timeout=timeout)
        except Exception as exc:
            results[scanner_name] = {"error": str(exc)}
            errors.append(f"llm_guard.{scanner_name}: {exc}")
            logger.exception("llm_guard_error", scanner=scanner_name)

    return {
        **state,
        "risk_flags": risk_flags,
        "errors": errors,
        "scanner_results": {
            **state.get("scanner_results", {}),
            "llm_guard": results,
        },
    }
