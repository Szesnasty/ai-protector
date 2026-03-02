"""Presidio PII scanner node — detects and optionally masks PII in user prompts.

Entity types detected:
- PERSON, EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, US_SSN,
  IP_ADDRESS, IBAN_CODE, LOCATION, DATE_TIME, NRP

Engines are lazy-initialized on first call (loads spaCy NER model).
Analysis runs via ``asyncio.to_thread()`` to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio

import structlog

from src.config import get_settings
from src.pipeline.nodes import timed_node
from src.pipeline.state import PipelineState

logger = structlog.get_logger()

# ── Entity types ──────────────────────────────────────────────────────

PII_ENTITIES: list[str] = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "US_SSN",
    "IP_ADDRESS",
    "IBAN_CODE",
    "LOCATION",
    "DATE_TIME",
    "NRP",
]

# ── Lazy-initialized engine singletons ────────────────────────────────

_analyzer: object | None = None  # AnalyzerEngine
_anonymizer: object | None = None  # AnonymizerEngine


def get_analyzer():  # noqa: ANN201
    """Return cached AnalyzerEngine, creating it on first call."""
    global _analyzer  # noqa: PLW0603
    if _analyzer is None:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider

        settings = get_settings()
        nlp_config = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": settings.presidio_language, "model_name": settings.presidio_spacy_model}],
        }
        provider = NlpEngineProvider(nlp_configuration=nlp_config)
        nlp_engine = provider.create_engine()

        logger.info("presidio_analyzer_init", model=settings.presidio_spacy_model)
        _analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
        logger.info("presidio_analyzer_ready")
    return _analyzer


def get_anonymizer():  # noqa: ANN201
    """Return cached AnonymizerEngine, creating it on first call."""
    global _anonymizer  # noqa: PLW0603
    if _anonymizer is None:
        from presidio_anonymizer import AnonymizerEngine

        _anonymizer = AnonymizerEngine()
        logger.info("presidio_anonymizer_ready")
    return _anonymizer


def reset_analyzer() -> None:
    """Reset analyzer singleton (for testing)."""
    global _analyzer  # noqa: PLW0603
    _analyzer = None


def reset_anonymizer() -> None:
    """Reset anonymizer singleton (for testing)."""
    global _anonymizer  # noqa: PLW0603
    _anonymizer = None


# ── Masking helper ────────────────────────────────────────────────────


async def mask_pii_in_messages(
    messages: list[dict],
    original_text: str,
    analyzer_results: list,
) -> list[dict]:
    """Replace PII in user messages with placeholders like <PERSON>, <EMAIL_ADDRESS>."""
    anonymizer = get_anonymizer()
    anonymized = await asyncio.to_thread(
        anonymizer.anonymize,
        text=original_text,
        analyzer_results=analyzer_results,
    )

    masked_messages = [msg.copy() for msg in messages]
    for msg in masked_messages:
        if msg["role"] == "user" and msg["content"] == original_text:
            msg["content"] = anonymized.text
            break
    return masked_messages


# ── Node ──────────────────────────────────────────────────────────────


@timed_node("presidio")
async def presidio_node(state: PipelineState) -> PipelineState:
    """Run Presidio PII analysis against the user message.

    Detected entities are written to ``risk_flags["pii"]`` and
    ``scanner_results["presidio"]``.  When ``pii_action == "mask"``,
    PII tokens in the user message are replaced with ``<ENTITY_TYPE>``
    placeholders and the result is stored in ``modified_messages``.
    """
    settings = get_settings()

    # Global kill switch
    if not settings.enable_presidio:
        return state

    text = state.get("user_message", "")
    if not text:
        return state

    thresholds = state.get("policy_config", {}).get("thresholds", {})
    pii_action: str = thresholds.get("pii_action", "flag")  # "flag" | "mask" | "block"

    try:
        analyzer = get_analyzer()
        results = await asyncio.to_thread(
            analyzer.analyze,
            text=text,
            language=settings.presidio_language,
            entities=PII_ENTITIES,
            score_threshold=settings.presidio_score_threshold,
        )
    except Exception as exc:
        logger.exception("presidio_analyzer_error")
        errors = list(state.get("errors", []))
        errors.append(f"presidio: {exc}")
        return {
            **state,
            "errors": errors,
            "scanner_results": {
                **state.get("scanner_results", {}),
                "presidio": {"error": str(exc)},
            },
        }

    entities_found = [
        {
            "entity_type": r.entity_type,
            "score": round(r.score, 4),
            "start": r.start,
            "end": r.end,
        }
        for r in results
    ]

    risk_flags: dict = {**state.get("risk_flags", {})}
    if entities_found:
        risk_flags["pii"] = [e["entity_type"] for e in entities_found]
        risk_flags["pii_count"] = len(entities_found)

    scanner_results = {
        **state.get("scanner_results", {}),
        "presidio": {
            "entities": entities_found,
            "pii_action": pii_action,
        },
    }

    updated: dict = {
        **state,
        "risk_flags": risk_flags,
        "scanner_results": scanner_results,
    }

    # Mask PII when configured
    if pii_action == "mask" and results:
        try:
            messages = state.get("messages", [])
            masked = await mask_pii_in_messages(messages, text, results)
            updated["modified_messages"] = masked
        except Exception as exc:
            logger.exception("presidio_masking_error")
            errors = list(state.get("errors", []))
            errors.append(f"presidio.mask: {exc}")
            updated["errors"] = errors

    return updated
