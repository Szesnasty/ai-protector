"""User input & tool output sanitizer — anti-spoofing defense layer.

Spec: docs/archive/agents/05-agents-role-separation/SPEC.md

Provides:
  - sanitize_user_input()  — strip role markers, control chars, normalize
  - sanitize_chat_history() — re-sanitize stored conversation turns
"""

from __future__ import annotations

import re
import unicodedata

# ── Role-spoofing patterns to strip ───────────────────────────────────

ROLE_SPOOFING_PATTERNS: list[re.Pattern[str]] = [
    # ChatML format
    re.compile(r"<\|im_start\|>\s*(system|assistant|user|tool)", re.IGNORECASE),
    re.compile(r"<\|im_end\|>"),
    # Llama / instruction format
    re.compile(r"\[INST\]"),
    re.compile(r"\[/INST\]"),
    re.compile(r"<<SYS>>"),
    re.compile(r"<</SYS>>"),
    # Markdown role markers (at line start)
    re.compile(r"^###\s*(system|assistant|user|tool)\s*:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(Human|Assistant|System|Tool)\s*:", re.IGNORECASE | re.MULTILINE),
    # Common injection framing
    re.compile(r"---\s*new\s+system\s+prompt\s*---", re.IGNORECASE),
    re.compile(r"---\s*override\s*---", re.IGNORECASE),
    # XML-style role tags
    re.compile(r"<\|?(system|assistant|user|tool)\|?>", re.IGNORECASE),
]

# ── Control characters to strip ───────────────────────────────────────
# Zero-width, bidi overrides, bidi isolates, BOM, soft hyphen

STRIP_CODEPOINTS: set[str] = {
    "\u200b",  # Zero-width space
    "\u200c",  # Zero-width non-joiner
    "\u200d",  # Zero-width joiner
    "\u2060",  # Word joiner
    "\u00ad",  # Soft hyphen
    "\ufeff",  # BOM / Zero-width no-break space
    # Bidi overrides
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    # Bidi isolates
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
}

# Regex matching any of the above codepoints (plus ASCII control chars except \n \t)
_CONTROL_RE = re.compile(
    "[" + "".join(re.escape(c) for c in STRIP_CODEPOINTS) + r"\x00-\x08\x0b\x0c\x0e-\x1f\x7f" + "]"
)

# Collapse excessive newlines (more than 2 consecutive)
_EXCESSIVE_NEWLINES_RE = re.compile(r"\n{3,}")

# Collapse excessive whitespace on a single line
_EXCESSIVE_SPACES_RE = re.compile(r"[ \t]{4,}")


# ── Public API ────────────────────────────────────────────────────────


def sanitize_user_input(text: str) -> str:
    """Sanitize user input: strip role spoofing, control chars, normalize.

    Steps:
      1. Unicode normalize (NFKC)
      2. Remove dangerous control characters
      3. Strip role-spoofing patterns
      4. Normalize whitespace
      5. Trim leading/trailing whitespace
    """
    if not text:
        return text

    # 1. Unicode normalize
    text = unicodedata.normalize("NFKC", text)

    # 2. Remove control characters
    text = _CONTROL_RE.sub("", text)

    # 3. Strip role-spoofing patterns
    for pattern in ROLE_SPOOFING_PATTERNS:
        text = pattern.sub("", text)

    # 4. Normalize whitespace
    text = _EXCESSIVE_NEWLINES_RE.sub("\n\n", text)
    text = _EXCESSIVE_SPACES_RE.sub("  ", text)

    # 5. Trim
    text = text.strip()

    return text


def sanitize_chat_history(
    history: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Re-sanitize stored chat history turns.

    - User messages: full sanitization
    - Assistant messages: only control char removal (trusted content)
    - Unknown roles: sanitized as user messages
    """
    sanitized: list[dict[str, str]] = []
    for turn in history:
        role = turn.get("role", "user")
        content = turn.get("content", "")

        if role == "assistant":
            # Light sanitization — strip control chars only
            content = _CONTROL_RE.sub("", content)
        else:
            # Full sanitization for user / unknown
            content = sanitize_user_input(content)

        sanitized.append({"role": role, "content": content})

    return sanitized
