"""Memory hygiene — sanitize conversation history by stripping PII, secrets, and truncating.

Prevents PII/secrets from accumulating in conversation windows across turns.
Used by ``output_filter_node`` and available for any future context-management system.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

logger = structlog.get_logger()

# ── Defaults ──────────────────────────────────────────────────────────

DEFAULT_MAX_TURNS = 20
"""Max non-system messages to keep (oldest are dropped)."""

DEFAULT_MAX_CHARS_PER_MESSAGE = 4000
"""Max characters per individual message content (~1 000 tokens)."""

DEFAULT_MAX_TOTAL_CHARS = 32000
"""Max total characters across all messages (~8 000 tokens)."""


# ── Public API ────────────────────────────────────────────────────────


async def sanitize_conversation(
    messages: list[dict[str, Any]],
    *,
    redact_pii: bool = True,
    redact_secrets: bool = True,
    max_turns: int = DEFAULT_MAX_TURNS,
    max_chars_per_message: int = DEFAULT_MAX_CHARS_PER_MESSAGE,
    max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
) -> list[dict[str, Any]]:
    """Return a sanitized copy of the conversation.

    Steps (in order):
    1. Truncate to *max_turns* (keep system messages + last N non-system).
    2. Truncate individual messages that exceed *max_chars_per_message*.
    3. Optionally redact PII from user/assistant contents (Presidio).
    4. Optionally redact secrets via regex.
    5. Enforce *max_total_chars* by dropping oldest non-system messages.
    """
    if not messages:
        return []

    cleaned = _truncate_turns(messages, max_turns)
    cleaned = _truncate_messages(cleaned, max_chars_per_message)

    if redact_pii:
        cleaned = await _redact_pii_from_messages(cleaned)
    if redact_secrets:
        cleaned = _redact_secrets_from_messages(cleaned)

    cleaned = _enforce_total_limit(cleaned, max_total_chars)
    return cleaned


# ── Turn truncation ──────────────────────────────────────────────────


def _truncate_turns(messages: list[dict], max_turns: int) -> list[dict]:
    """Keep system message(s) + last *max_turns* non-system messages."""
    system_msgs = [m.copy() for m in messages if m.get("role") == "system"]
    non_system = [m.copy() for m in messages if m.get("role") != "system"]

    if len(non_system) > max_turns:
        non_system = non_system[-max_turns:]

    return system_msgs + non_system


# ── Per-message truncation ───────────────────────────────────────────


def _truncate_messages(messages: list[dict], max_chars: int) -> list[dict]:
    """Truncate individual messages that exceed *max_chars*."""
    result: list[dict] = []
    for msg in messages:
        m = msg.copy()
        content = m.get("content", "")
        if isinstance(content, str) and len(content) > max_chars:
            m["content"] = content[:max_chars] + "... [TRUNCATED]"
        result.append(m)
    return result


# ── PII redaction (Presidio) ─────────────────────────────────────────


async def _redact_pii_from_messages(messages: list[dict]) -> list[dict]:
    """Run Presidio on each user/assistant message and anonymise PII."""
    from src.pipeline.nodes.presidio import PII_ENTITIES, get_analyzer, get_anonymizer

    try:
        analyzer = get_analyzer()
        anonymizer = get_anonymizer()
    except Exception:
        logger.warning("memory_hygiene_presidio_unavailable")
        return messages

    settings_mod = __import__("src.config", fromlist=["get_settings"])
    settings = settings_mod.get_settings()

    result: list[dict] = []
    for msg in messages:
        m = msg.copy()
        content = m.get("content", "")
        if content and msg.get("role") in ("user", "assistant"):
            try:
                entities = await asyncio.to_thread(
                    analyzer.analyze,
                    text=content,
                    language=settings.presidio_language,
                    entities=PII_ENTITIES,
                    score_threshold=settings.presidio_score_threshold,
                )
                if entities:
                    anonymized = await asyncio.to_thread(
                        anonymizer.anonymize,
                        text=content,
                        analyzer_results=entities,
                    )
                    m["content"] = anonymized.text
            except Exception:
                logger.warning("memory_hygiene_pii_redact_failed", role=msg.get("role"))
        result.append(m)

    return result


# ── Secret redaction ─────────────────────────────────────────────────


def _redact_secrets_from_messages(messages: list[dict]) -> list[dict]:
    """Regex-replace secrets in all message contents."""
    from src.pipeline.nodes.output_filter import SECRET_PATTERNS

    result: list[dict] = []
    for msg in messages:
        m = msg.copy()
        content = m.get("content", "")
        if isinstance(content, str):
            for pattern, replacement in SECRET_PATTERNS:
                content = pattern.sub(replacement, content)
            m["content"] = content
        result.append(m)
    return result


# ── Total conversation limit ─────────────────────────────────────────


def _enforce_total_limit(messages: list[dict], max_total_chars: int) -> list[dict]:
    """Drop oldest non-system messages until total chars is under limit."""
    total = sum(len(m.get("content", "") or "") for m in messages)
    if total <= max_total_chars:
        return messages

    system = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]

    while non_system and total > max_total_chars:
        dropped = non_system.pop(0)
        total -= len(dropped.get("content", "") or "")

    return system + non_system
