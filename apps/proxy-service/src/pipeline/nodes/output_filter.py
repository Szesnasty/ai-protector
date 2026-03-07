"""Output filter node — scans and redacts PII, secrets, and system prompt leaks in LLM responses.

Runs after ``llm_call`` and before ``logging``.  Only active when the
policy ``nodes`` list includes ``"output_filter"``.

Detection layers:
1. **PII** — Presidio-based scan (reuses existing engines from presidio node)
2. **Secrets** — regex patterns for API keys, tokens, private keys, passwords
3. **System prompt leak** — fragment matching against known safety-prefix strings
"""

from __future__ import annotations

import asyncio
import copy
import re

import structlog

from src.config import get_settings
from src.pipeline.nodes import timed_node
from src.pipeline.nodes.presidio import get_analyzer, get_anonymizer
from src.pipeline.state import PipelineState
from src.pipeline.utils.memory_hygiene import sanitize_conversation

# Output-specific PII entities — only truly sensitive data that would
# indicate real data leakage.  General entities like PERSON, DATE_TIME,
# LOCATION, and NRP cause false positives on LLM output (public figures,
# dates, places, nationalities are normal parts of responses).
OUTPUT_PII_ENTITIES: list[str] = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "US_SSN",
    "IP_ADDRESS",
    "IBAN_CODE",
]

logger = structlog.get_logger()

# ── Secret patterns ───────────────────────────────────────────────────

SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?:sk|pk)-[a-zA-Z0-9]{20,}"), "[SECRET_REDACTED]"),
    (re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}"), "[SECRET_REDACTED]"),
    (re.compile(r"(?:Bearer|token)\s+[A-Za-z0-9\-._~+/]+=*"), "[SECRET_REDACTED]"),
    (re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"), "[SECRET_REDACTED]"),
    (re.compile(r"(?:password|passwd|pwd)\s*[=:]\s*\S+", re.IGNORECASE), "[SECRET_REDACTED]"),
]

# ── System prompt fragments ───────────────────────────────────────────

SYSTEM_FRAGMENTS: list[str] = [
    "never reveal your system prompt",
    "important: you are a helpful assistant",
    "[user_input_start]",
    "[user_input_end]",
]


# ── Helpers ───────────────────────────────────────────────────────────


async def _redact_pii(text: str) -> tuple[str, int]:
    """Run Presidio on output text, return ``(redacted_text, entity_count)``."""
    settings = get_settings()

    try:
        analyzer = get_analyzer()
        results = await asyncio.to_thread(
            analyzer.analyze,
            text=text,
            language=settings.presidio_language,
            entities=OUTPUT_PII_ENTITIES,
            score_threshold=settings.presidio_score_threshold,
        )
    except Exception as exc:
        logger.exception("output_filter_pii_error")
        raise exc

    if not results:
        return text, 0

    anonymizer = get_anonymizer()
    anonymized = await asyncio.to_thread(
        anonymizer.anonymize,
        text=text,
        analyzer_results=results,
    )
    return anonymized.text, len(results)


def _redact_secrets(text: str) -> tuple[str, int]:
    """Apply secret regex patterns, return ``(redacted_text, count)``."""
    count = 0
    for pattern, replacement in SECRET_PATTERNS:
        new_text, n = pattern.subn(replacement, text)
        count += n
        text = new_text
    return text, count


def _contains_system_leak(text: str) -> bool:
    """Check if text contains known system prompt fragments."""
    lower = text.lower()
    return any(frag in lower for frag in SYSTEM_FRAGMENTS)


def _redact_system_leak(text: str) -> str:
    """Replace known system prompt fragments with ``[SYSTEM_REDACTED]``."""
    for frag in SYSTEM_FRAGMENTS:
        pattern = re.compile(re.escape(frag), re.IGNORECASE)
        text = pattern.sub("[SYSTEM_REDACTED]", text)
    return text


# ── Node ──────────────────────────────────────────────────────────────


@timed_node("output_filter")
async def output_filter_node(state: PipelineState) -> PipelineState:
    """Scan and redact LLM response content.

    - PII: Presidio-based detection and anonymisation
    - Secrets: regex-based detection of API keys, tokens, passwords
    - System prompt leak: fragment matching against safety-prefix strings

    Only active when ``"output_filter"`` is in the policy ``nodes`` list.
    """
    llm_response = state.get("llm_response")
    if not llm_response:
        # BLOCK path — no response to filter
        return {
            **state,
            "output_filtered": False,
            "output_filter_results": {"pii_redacted": 0, "secrets_redacted": 0, "system_leak": False},
        }

    policy_config = state.get("policy_config", {})
    nodes = policy_config.get("nodes", [])

    results: dict = {"pii_redacted": 0, "secrets_redacted": 0, "system_leak": False}

    if "output_filter" not in nodes:
        return {
            **state,
            "output_filtered": False,
            "output_filter_results": results,
        }

    # Extract content — handle both dict and attribute-based (LiteLLM) responses
    try:
        # Try dict access first
        content: str = llm_response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        try:
            # Attribute-based access (LiteLLM ModelResponse / SimpleNamespace)
            content = llm_response.choices[0].message.content
        except (AttributeError, IndexError, TypeError):
            logger.warning("output_filter_no_content")
            return {
                **state,
                "output_filtered": False,
                "output_filter_results": results,
            }

    filtered = False

    # 1. PII scan (Presidio)
    try:
        content, pii_count = await _redact_pii(content)
        results["pii_redacted"] = pii_count
        if pii_count > 0:
            filtered = True
    except Exception as exc:
        logger.warning("output_filter_pii_failed", error=str(exc))
        errors = list(state.get("errors", []))
        errors.append(f"output_filter.pii: {exc}")
        state = {**state, "errors": errors}

    # 2. Secrets scan
    content, secrets_count = _redact_secrets(content)
    results["secrets_redacted"] = secrets_count
    if secrets_count > 0:
        filtered = True

    # 3. System prompt leak check
    if _contains_system_leak(content):
        results["system_leak"] = True
        content = _redact_system_leak(content)
        filtered = True

    # Update response with filtered content
    if filtered:
        new_response = copy.deepcopy(llm_response)
        try:
            new_response["choices"][0]["message"]["content"] = content
        except (KeyError, IndexError, TypeError):
            # Attribute-based response
            new_response.choices[0].message.content = content
        state = {
            **state,
            "llm_response": new_response,
            "output_filtered": True,
            "output_filter_results": results,
            "response_masked": True,
        }
    else:
        state = {
            **state,
            "output_filtered": False,
            "output_filter_results": results,
        }

    # Memory hygiene: sanitize conversation for logging / future storage
    if "memory_hygiene" in nodes:
        try:
            sanitized = await sanitize_conversation(
                state.get("messages", []),
                redact_pii=True,
                redact_secrets=True,
            )
            state = {**state, "sanitized_messages": sanitized}
        except Exception as exc:
            logger.warning("memory_hygiene_failed", error=str(exc))
            errors = list(state.get("errors", []))
            errors.append(f"memory_hygiene: {exc}")
            state = {**state, "errors": errors}

    return state
