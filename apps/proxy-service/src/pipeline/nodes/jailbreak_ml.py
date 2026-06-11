"""Jailbreak ML classifier node (A1) — semantic jailbreak detection.

Closes the gap that pattern matching and the injection model leave open:
roleplay / PAIR-style jailbreaks that carry no obvious attack keywords. Uses a
small DistilBERT classifier (``madhurjindal/Jailbreak-Detector``) that labels a
prompt ``jailbreak`` or ``benign``.

Runs on ``scan_text`` so it also benefits from the A2 deobfuscation layer. The
model is lazy-loaded once and preloaded at startup (see main.py).
"""

from __future__ import annotations

import asyncio
import threading

import structlog

from src.config import get_settings
from src.pipeline.nodes import timed_node
from src.pipeline.state import PipelineState

logger = structlog.get_logger()

_classifier = None  # lazy singleton
_load_lock = threading.Lock()  # guards lazy init against concurrent first requests
_infer_lock = threading.Lock()  # serializes inference — one pipeline is not thread-safe


def get_classifier():
    """Load (once) and return the jailbreak text-classification pipeline."""
    global _classifier  # noqa: PLW0603
    if _classifier is None:
        with _load_lock:
            if _classifier is None:  # double-checked
                settings = get_settings()
                from transformers import pipeline

                logger.info("jailbreak_ml_init", model=settings.jailbreak_ml_model)
                _classifier = pipeline(
                    "text-classification",
                    model=settings.jailbreak_ml_model,
                    truncation=True,
                    max_length=512,
                )
                logger.info("jailbreak_ml_ready")
    return _classifier


def _classify(text: str):
    """Run the classifier under the inference lock (thread-safe)."""
    with _infer_lock:
        return get_classifier()(text)


def reset_classifier() -> None:
    """Reset the singleton (for testing)."""
    global _classifier  # noqa: PLW0603
    _classifier = None


@timed_node("jailbreak_ml")
async def jailbreak_ml_node(state: PipelineState) -> PipelineState:
    """Flag the prompt when the classifier labels it a jailbreak with high confidence."""
    settings = get_settings()
    if not settings.enable_jailbreak_ml:
        return state

    text = state.get("scan_text") or state.get("user_message", "")
    if not text:
        return state

    risk_flags: dict = {**state.get("risk_flags", {})}
    scanner_results: dict = {**state.get("scanner_results", {})}
    errors: list[str] = list(state.get("errors", []))
    threshold = (
        state.get("policy_config", {})
        .get("thresholds", {})
        .get("jailbreak_ml_threshold", settings.jailbreak_ml_threshold)
    )

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_classify, text[:2000]),
            timeout=settings.scanner_timeout,
        )
        top = result[0] if isinstance(result, list) else result
        label = str(top.get("label", "")).lower()
        score = float(top.get("score", 0.0))
        is_jailbreak = label == "jailbreak" and score >= threshold

        scanner_results["jailbreak_ml"] = {"label": label, "score": round(score, 4)}
        if is_jailbreak:
            risk_flags["jailbreak_ml"] = round(score, 4)
            logger.warning("jailbreak_ml_flag", score=round(score, 4), request_id=state.get("request_id"))
    except TimeoutError:
        errors.append(f"jailbreak_ml: timeout after {settings.scanner_timeout}s")
        logger.error("jailbreak_ml_timeout")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"jailbreak_ml: {exc}")
        logger.error("jailbreak_ml_error", error_type=type(exc).__name__)

    return {
        **state,
        "risk_flags": risk_flags,
        "scanner_results": scanner_results,
        "errors": errors,
    }
