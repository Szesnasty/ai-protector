"""RulesNode — deterministic checks: denylist, length, encoding, special chars."""

from __future__ import annotations

import re

from src.pipeline.nodes import timed_node
from src.pipeline.state import PipelineState
from src.services.denylist import check_denylist

# ── Thresholds ────────────────────────────────────────────────────────
MAX_PROMPT_LENGTH = 16_000  # characters
MAX_MESSAGES = 50
SPECIAL_CHAR_THRESHOLD = 0.3  # ratio of non-alnum/non-space chars

# Severity → risk score boost mapping
SEVERITY_SCORE = {"low": 0.1, "medium": 0.2, "high": 0.3, "critical": 0.5}


# ── Pattern helpers ───────────────────────────────────────────────────


def contains_encoded_content(text: str) -> bool:
    """Detect base64 or hex-encoded content used for obfuscation."""
    # Base64 pattern (>40 chars of base64 alphabet)
    if re.search(r"[A-Za-z0-9+/]{40,}={0,2}", text):
        return True
    # Hex-encoded strings (>20 hex chars)
    return bool(re.search(r"(?:0x)?[0-9a-fA-F]{20,}", text))


def excessive_special_chars(text: str) -> bool:
    """Detect prompts with >30 % non-alphanumeric characters."""
    if len(text) < 10:
        return False
    special = sum(1 for c in text if not c.isalnum() and not c.isspace())
    return (special / len(text)) > SPECIAL_CHAR_THRESHOLD


# ── Node ──────────────────────────────────────────────────────────────


@timed_node("rules")
async def rules_node(state: PipelineState) -> PipelineState:
    """Run deterministic rule checks and populate rules_matched / risk_flags."""
    matched: list[str] = list(state.get("rules_matched", []))
    risk_flags: dict = {**state.get("risk_flags", {})}
    text = state.get("user_message", "")
    messages = state.get("messages", [])

    # 1. Denylist — returns DenylistHit with action/severity
    policy_name = state.get("policy_name", "balanced")
    denylist_hits = await check_denylist(text, policy_name)
    for hit in denylist_hits:
        if hit.action == "block":
            matched.append(f"denylist:{hit.phrase}")
            risk_flags["denylist_hit"] = True
        elif hit.action == "flag":
            custom_flags = risk_flags.get("custom_flags", [])
            custom_flags.append(
                {
                    "phrase": hit.phrase,
                    "category": hit.category,
                    "severity": hit.severity,
                    "description": hit.description,
                }
            )
            risk_flags["custom_flags"] = custom_flags
        elif hit.action == "score_boost":
            boost = SEVERITY_SCORE.get(hit.severity, 0.2)
            risk_flags["score_boost"] = risk_flags.get("score_boost", 0.0) + boost

    # 2. Prompt length
    if len(text) > MAX_PROMPT_LENGTH:
        matched.append("length_exceeded")
        risk_flags["length_exceeded"] = len(text)

    # 3. Messages count
    if len(messages) > MAX_MESSAGES:
        matched.append("too_many_messages")
        risk_flags["too_many_messages"] = len(messages)

    # 4. Encoded content
    if contains_encoded_content(text):
        matched.append("encoded_content")
        risk_flags["encoded_content"] = True

    # 5. Excessive special characters
    if excessive_special_chars(text):
        matched.append("excessive_special_chars")
        risk_flags["special_chars"] = True

    return {**state, "rules_matched": matched, "risk_flags": risk_flags}
