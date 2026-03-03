# Step 09b — Memory Hygiene Node

| | |
|---|---|
| **Parent** | [Step 09 — Output Pipeline](SPEC.md) |
| **Estimated time** | 1.5–2 hours |
| **Depends on** | Step 09a (output filter — Presidio reuse) |

---

## Goal

Create a **memory hygiene** utility that sanitizes conversation history before it is either:
1. **Stored** (if a future memory/context store is added)
2. **Sent as context** to the LLM in multi-turn conversations

This prevents PII/secrets from accumulating in conversation windows across turns. For MVP, this is implemented as a sub-module (not a separate graph node) called from `output_filter_node`.

---

## Why not a separate graph node?

Memory hygiene operates on the same data (response text) as output filtering, using the same tools (Presidio, secret patterns). Adding a separate node would:
- Duplicate Presidio initialization
- Add an extra state copy
- Complicate the graph for minimal benefit

Instead, `memory_hygiene` is a **utility module** that can be called from the output filter or from any future context management system.

---

## Scope

### In scope
- New file `src/pipeline/utils/memory_hygiene.py`
- Sanitize conversation messages: strip PII and secrets from content
- Truncate long conversations to configurable max turns/tokens
- Provide a clean conversation history for audit logging (no raw PII in DB)
- Unit tests

### Out of scope
- Persistent conversation memory store (future step)
- Per-user conversation tracking
- Semantic deduplication of messages
- Token counting with tiktoken (use character-based approximation for MVP)

---

## Technical Design

### Module: `src/pipeline/utils/memory_hygiene.py`

```python
from __future__ import annotations

import re
from typing import Any

import structlog

logger = structlog.get_logger()

# Max conversation turns to keep (system + last N user/assistant pairs)
DEFAULT_MAX_TURNS = 20
# Max characters per message content (~4 chars ≈ 1 token)
DEFAULT_MAX_CHARS_PER_MESSAGE = 4000
# Total max characters for full conversation
DEFAULT_MAX_TOTAL_CHARS = 32000


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
    
    1. Truncate to max_turns (keep system message + last N)
    2. Truncate individual messages that exceed max_chars
    3. Redact PII from all message contents
    4. Redact secrets from all message contents
    """
    cleaned = _truncate_turns(messages, max_turns)
    cleaned = _truncate_messages(cleaned, max_chars_per_message)
    
    if redact_pii:
        cleaned = await _redact_pii_from_messages(cleaned)
    if redact_secrets:
        cleaned = _redact_secrets_from_messages(cleaned)
    
    cleaned = _enforce_total_limit(cleaned, max_total_chars)
    return cleaned
```

### Turn truncation

```python
def _truncate_turns(
    messages: list[dict], max_turns: int
) -> list[dict]:
    """Keep system message(s) + last max_turns messages."""
    system_msgs = [m.copy() for m in messages if m["role"] == "system"]
    non_system = [m.copy() for m in messages if m["role"] != "system"]
    
    if len(non_system) > max_turns:
        non_system = non_system[-max_turns:]
    
    return system_msgs + non_system
```

### Message truncation

```python
def _truncate_messages(
    messages: list[dict], max_chars: int
) -> list[dict]:
    """Truncate individual messages exceeding max_chars."""
    result = []
    for msg in messages:
        m = msg.copy()
        content = m.get("content", "")
        if len(content) > max_chars:
            m["content"] = content[:max_chars] + "... [TRUNCATED]"
        result.append(m)
    return result
```

### PII redaction (Presidio reuse)

```python
async def _redact_pii_from_messages(messages: list[dict]) -> list[dict]:
    """Run Presidio on each message content and anonymize."""
    from src.pipeline.nodes.presidio import get_analyzer, get_anonymizer
    
    analyzer = get_analyzer()
    anonymizer = get_anonymizer()
    result = []
    
    for msg in messages:
        m = msg.copy()
        content = m.get("content", "")
        if content and msg["role"] in ("user", "assistant"):
            entities = analyzer.analyze(text=content, language="en")
            if entities:
                anonymized = anonymizer.anonymize(text=content, analyzer_results=entities)
                m["content"] = anonymized.text
        result.append(m)
    
    return result
```

### Secret redaction

```python
from src.pipeline.nodes.output_filter import SECRET_PATTERNS

def _redact_secrets_from_messages(messages: list[dict]) -> list[dict]:
    """Regex-replace secrets in all messages."""
    result = []
    for msg in messages:
        m = msg.copy()
        content = m.get("content", "")
        for pattern, replacement in SECRET_PATTERNS:
            content = re.sub(pattern, replacement, content)
        m["content"] = content
        result.append(m)
    return result
```

### Total conversation limit

```python
def _enforce_total_limit(
    messages: list[dict], max_total_chars: int
) -> list[dict]:
    """Drop oldest non-system messages until total chars is under limit."""
    total = sum(len(m.get("content", "")) for m in messages)
    if total <= max_total_chars:
        return messages
    
    system = [m for m in messages if m["role"] == "system"]
    non_system = [m for m in messages if m["role"] != "system"]
    
    while non_system and total > max_total_chars:
        dropped = non_system.pop(0)
        total -= len(dropped.get("content", ""))
    
    return system + non_system
```

---

## Integration with output_filter

In `output_filter_node` (09a), after filtering the response:

```python
# Optional: sanitize the full conversation for logging
from src.pipeline.utils.memory_hygiene import sanitize_conversation

sanitized_messages = await sanitize_conversation(
    state["messages"],
    redact_pii=("output_filter" in nodes),
    redact_secrets=True,
)
# Store sanitized version for logging node
state["sanitized_messages"] = sanitized_messages
```

### New state field

```python
# PipelineState addition
sanitized_messages: list[dict] | None  # Conversation with PII/secrets stripped
```

---

## Policy configuration

Memory hygiene settings can be added to policy thresholds:

```json
{
  "thresholds": {
    "max_risk": 0.5,
    "pii_action": "mask",
    "max_conversation_turns": 20,
    "max_message_chars": 4000
  }
}
```

For MVP, defaults are used. Policy-driven overrides are optional enhancement.

---

## Tests

### Unit tests (`tests/pipeline/utils/test_memory_hygiene.py`)

| # | Test | Assert |
|---|------|--------|
| 1 | Short conversation → no changes | Same messages returned |
| 2 | 30 messages → truncated to 20 + system | System kept, oldest dropped |
| 3 | Long message → truncated with `[TRUNCATED]` | Content ends with marker |
| 4 | Message with email → PII redacted | Email replaced |
| 5 | Message with API key → secret redacted | `[SECRET_REDACTED]` |
| 6 | System message preserved during truncation | Always in result |
| 7 | Total char limit exceeded → oldest dropped | Under limit |
| 8 | `redact_pii=False` → PII kept | Email still present |
| 9 | `redact_secrets=False` → secrets kept | API key present |
| 10 | Empty conversation → empty list | No error |
| 11 | Mixed redaction: PII + secrets in same message | Both redacted |

---

## Files to create/modify

| Action | File |
|--------|------|
| **Create** | `src/pipeline/utils/__init__.py` |
| **Create** | `src/pipeline/utils/memory_hygiene.py` |
| **Create** | `tests/pipeline/utils/__init__.py` |
| **Create** | `tests/pipeline/utils/test_memory_hygiene.py` |
| **Modify** | `src/pipeline/state.py` — add `sanitized_messages` |
| *(09a)* | `src/pipeline/nodes/output_filter.py` — call `sanitize_conversation` |

---

## Definition of Done

- [ ] `sanitize_conversation()` truncates turns and messages
- [ ] PII redaction via Presidio works on conversation history
- [ ] Secret redaction reuses patterns from output_filter
- [ ] Total conversation size limit enforced
- [ ] All 11 unit tests pass
- [ ] `ruff check` clean
