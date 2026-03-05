"""Post-tool Enforcement Gate — security gate on tool output.

Spec: docs/agents/03-agents-post-tool-enforcement/SPEC.md

For EACH tool result, runs a chain of scanners:
  1. PII detection — emails, phones, SSNs, credit cards, IP addresses
  2. Secrets detection — API keys, tokens, passwords, connection strings
  3. Injection detection — indirect prompt injection patterns in tool output
  4. Data size check — truncate oversized output

Returns a decision per tool result: PASS | REDACT | TRUNCATE | BLOCK.
The sanitized result is what goes to the LLM — never the raw output.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from src.agent.state import AgentState, PostGateResult, ToolCallRecord

logger = structlog.get_logger()

# ── Configuration ─────────────────────────────────────────────────────

MAX_TOOL_OUTPUT_SIZE = 4000  # Characters — truncate above this

PII_REPLACEMENT_TAG = "[PII:{entity_type}]"
SECRET_REPLACEMENT = "[SECRET:REDACTED]"
BLOCK_REPLACEMENT = (
    "[BLOCKED: Tool output contained potentially unsafe content and was not forwarded.]"
)

# ── PII Patterns ──────────────────────────────────────────────────────
# Lightweight regex-based PII detection (no Presidio dependency).
# Each entry: (entity_type, compiled regex)

PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "EMAIL",
        re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        ),
    ),
    (
        "PHONE",
        re.compile(
            r"(?<!\d)"  # not preceded by digit
            r"(?:\+?1[-.\s]?)?"  # optional country code
            r"(?:\(?\d{3}\)?[-.\s]?)"  # area code
            r"\d{3}[-.\s]?\d{4}"
            r"(?!\d)",  # not followed by digit
        ),
    ),
    (
        "SSN",
        re.compile(
            r"\b\d{3}-\d{2}-\d{4}\b"
        ),
    ),
    (
        "CREDIT_CARD",
        re.compile(
            r"\b(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6(?:011|5\d{2}))"
            r"[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{3,4}\b"
        ),
    ),
    (
        "IP_ADDRESS",
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
        ),
    ),
    (
        "IBAN",
        re.compile(
            r"\b[A-Z]{2}\d{2}\s?[\dA-Z]{4}\s?[\dA-Z]{4}\s?[\dA-Z]{4}"
            r"(?:\s?[\dA-Z]{4}){0,4}\s?[\dA-Z]{1,4}\b"
        ),
    ),
]

# ── Secrets Patterns ──────────────────────────────────────────────────

SECRETS_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "API_KEY",
        re.compile(
            r"\b(?:sk|pk|api|key|token|secret|access)[_-]"
            r"[A-Za-z0-9]{16,}\b",
            re.IGNORECASE,
        ),
    ),
    (
        "AWS_KEY",
        re.compile(r"\b(?:AKIA|ABIA|ACCA)[A-Z0-9]{16}\b"),
    ),
    (
        "GENERIC_SECRET",
        re.compile(
            r"(?:password|passwd|pwd|secret|token|api_key|apikey|access_key|private_key)"
            r"\s*[:=]\s*['\"]?[^\s'\"]{8,}",
            re.IGNORECASE,
        ),
    ),
    (
        "JWT",
        re.compile(
            r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
        ),
    ),
    (
        "CONNECTION_STRING",
        re.compile(
            r"(?:postgres|mysql|mongodb|redis|amqp)://[^\s\"']+",
            re.IGNORECASE,
        ),
    ),
    (
        "PRIVATE_KEY",
        re.compile(
            r"-----BEGIN\s(?:RSA\s)?PRIVATE\sKEY-----",
        ),
    ),
]

# ── Injection Patterns (indirect prompt injection in tool output) ─────

INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore_instructions",
        re.compile(
            r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE
        ),
    ),
    (
        "role_switch",
        re.compile(
            r"you\s+are\s+now\b", re.IGNORECASE
        ),
    ),
    (
        "new_system_prompt",
        re.compile(
            r"new\s+system\s+prompt", re.IGNORECASE
        ),
    ),
    (
        "reveal_prompt",
        re.compile(
            r"reveal\s+(your\s+)?(system\s+)?prompt", re.IGNORECASE
        ),
    ),
    (
        "disregard",
        re.compile(
            r"disregard\s+(all\s+)?(prior|previous|above)", re.IGNORECASE
        ),
    ),
    (
        "override_rules",
        re.compile(
            r"override\s+(all\s+)?rules", re.IGNORECASE
        ),
    ),
    (
        "act_as_unrestricted",
        re.compile(
            r"act\s+as\s+(an?\s+)?unrestricted", re.IGNORECASE
        ),
    ),
    (
        "do_anything_now",
        re.compile(
            r"do\s+anything\s+now", re.IGNORECASE
        ),
    ),
    (
        "jailbreak",
        re.compile(
            r"\bjailbreak\b", re.IGNORECASE
        ),
    ),
    (
        "special_token_im",
        re.compile(r"<\|im_start\|>"),
    ),
    (
        "special_token_inst",
        re.compile(r"\[INST\]"),
    ),
    (
        "special_token_sys",
        re.compile(r"<<SYS>>"),
    ),
    (
        "role_header",
        re.compile(
            r"###\s*(system|assistant)\s*:", re.IGNORECASE
        ),
    ),
    (
        "pretend_to_be",
        re.compile(
            r"pretend\s+to\s+be\b", re.IGNORECASE
        ),
    ),
    (
        "do_not_follow",
        re.compile(
            r"do\s+not\s+follow\s+(your\s+)?instructions", re.IGNORECASE
        ),
    ),
]

# Injection score thresholds
INJECTION_BLOCK_THRESHOLD = 0.4  # Block if score >= this


# ── Individual Scanners ───────────────────────────────────────────────


def scan_pii(text: str) -> tuple[str, list[dict[str, Any]], int]:
    """Scan text for PII and redact matches.

    Returns (redacted_text, pii_entities, redactions_count).
    """
    entities: list[dict[str, Any]] = []
    redacted = text

    for entity_type, pattern in PII_PATTERNS:
        for match in pattern.finditer(text):
            entities.append({
                "type": entity_type,
                "start": match.start(),
                "end": match.end(),
                "text_preview": match.group()[:4] + "***",
            })

        replacement = f"[PII:{entity_type}]"
        redacted = pattern.sub(replacement, redacted)

    return redacted, entities, len(entities)


def scan_secrets(text: str) -> tuple[str, int]:
    """Scan text for secrets/credentials and redact matches.

    Returns (redacted_text, secrets_count).
    """
    redacted = text
    count = 0

    for _secret_type, pattern in SECRETS_PATTERNS:
        matches = pattern.findall(redacted)
        count += len(matches)
        redacted = pattern.sub(SECRET_REPLACEMENT, redacted)

    return redacted, count


def scan_injection(text: str) -> tuple[float, list[str]]:
    """Scan text for indirect prompt injection patterns.

    Returns (injection_score, matched_pattern_names).
    Score is 0.0–1.0 based on the number and severity of matched patterns.
    """
    matched: list[str] = []

    for pattern_name, pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            matched.append(pattern_name)

    if not matched:
        return 0.0, []

    # Score: each match adds ~0.2, special tokens add extra weight
    high_severity = {"special_token_im", "special_token_inst", "special_token_sys", "role_header"}
    score = 0.0
    for name in matched:
        score += 0.3 if name in high_severity else 0.2

    return min(score, 1.0), matched


def check_size(text: str, max_size: int = MAX_TOOL_OUTPUT_SIZE) -> tuple[str, bool]:
    """Check and truncate oversized text.

    Returns (possibly_truncated_text, was_truncated).
    """
    if len(text) <= max_size:
        return text, False

    truncated = text[:max_size] + (
        f"\n[TRUNCATED: {len(text)} chars, showing first {max_size}]"
    )
    return truncated, True


# ── Per-result Gate ───────────────────────────────────────────────────


def evaluate_tool_output(
    tool_name: str,
    raw_result: str,
) -> tuple[str, PostGateResult]:
    """Run all scanners on a single tool result.

    Returns (sanitized_result, post_gate_result).
    """
    original_length = len(raw_result)
    working = raw_result
    total_redactions = 0

    # ── 1. Injection check (check on raw, before redaction) ─────
    injection_score, injection_patterns = scan_injection(raw_result)

    if injection_score >= INJECTION_BLOCK_THRESHOLD:
        logger.warning(
            "post_tool_gate_injection_blocked",
            tool=tool_name,
            score=injection_score,
            patterns=injection_patterns,
        )
        return BLOCK_REPLACEMENT, PostGateResult(
            decision="BLOCK",
            pii_entities=[],
            pii_count=0,
            secrets_count=0,
            injection_score=injection_score,
            injection_patterns=injection_patterns,
            original_length=original_length,
            sanitized_length=len(BLOCK_REPLACEMENT),
            redactions_applied=0,
            reason=f"Injection detected (score={injection_score:.2f}): {', '.join(injection_patterns)}",
        )

    # ── 2. PII scan ─────────────────────────────────────────────
    working, pii_entities, pii_count = scan_pii(working)
    total_redactions += pii_count

    # ── 3. Secrets scan ─────────────────────────────────────────
    working, secrets_count = scan_secrets(working)
    total_redactions += secrets_count

    # ── 4. Size check ───────────────────────────────────────────
    working, was_truncated = check_size(working)

    # ── Decision ────────────────────────────────────────────────
    if was_truncated and total_redactions > 0:
        decision = "REDACT"  # Redaction takes priority in the label
    elif was_truncated:
        decision = "TRUNCATE"
    elif total_redactions > 0:
        decision = "REDACT"
    else:
        decision = "PASS"

    reason = None
    if decision == "REDACT":
        parts = []
        if pii_count:
            parts.append(f"{pii_count} PII entities")
        if secrets_count:
            parts.append(f"{secrets_count} secrets")
        reason = f"Redacted: {', '.join(parts)}"
    elif decision == "TRUNCATE":
        reason = f"Truncated from {original_length} to {len(working)} chars"

    return working, PostGateResult(
        decision=decision,
        pii_entities=pii_entities,
        pii_count=pii_count,
        secrets_count=secrets_count,
        injection_score=injection_score,
        injection_patterns=injection_patterns,
        original_length=original_length,
        sanitized_length=len(working),
        redactions_applied=total_redactions,
        reason=reason,
    )


# ── Gate Node ─────────────────────────────────────────────────────────


def post_tool_gate_node(state: AgentState) -> AgentState:
    """Post-tool enforcement gate — scans each tool result.

    Reads `tool_calls` from state, scans each allowed result,
    writes `sanitized_result` and `post_gate` onto each record.
    """
    tool_calls: list[ToolCallRecord] = list(state.get("tool_calls", []))
    updated_calls: list[ToolCallRecord] = []

    pass_count = 0
    redact_count = 0
    truncate_count = 0
    block_count = 0

    for tc in tool_calls:
        # Only scan allowed tool calls (denied ones have no real output)
        if not tc.get("allowed", False):
            updated_calls.append(tc)
            continue

        raw_result = tc.get("result", "")
        sanitized, post_gate = evaluate_tool_output(tc["tool"], raw_result)

        # Merge into a new record (preserve all existing fields)
        updated: ToolCallRecord = {
            **tc,  # type: ignore[typeddict-item]
            "sanitized_result": sanitized,
            "post_gate": post_gate,
        }
        updated_calls.append(updated)

        # Counters
        match post_gate.get("decision"):
            case "PASS":
                pass_count += 1
            case "REDACT":
                redact_count += 1
            case "TRUNCATE":
                truncate_count += 1
            case "BLOCK":
                block_count += 1

        logger.info(
            "post_tool_gate",
            tool=tc["tool"],
            decision=post_gate.get("decision"),
            pii_count=post_gate.get("pii_count", 0),
            secrets_count=post_gate.get("secrets_count", 0),
            injection_score=post_gate.get("injection_score", 0.0),
            reason=post_gate.get("reason"),
        )

    logger.info(
        "post_tool_gate_summary",
        total=len(tool_calls),
        passed=pass_count,
        redacted=redact_count,
        truncated=truncate_count,
        blocked=block_count,
    )

    return {
        **state,
        "tool_calls": updated_calls,
    }
