"""Deterministic obfuscation strategies.

These mirror promptfoo's encoding strategies (``base64``, ``leetspeak``,
``rot13``, ``homoglyph``, ``multilingual``) and are fully deterministic — no LLM,
no randomness — so the corpus they produce is reproducible and replay-stable.

This module doubles as the reference transform set for the A2 deobfuscation
work: every strategy here is something A2's normalization layer must defeat.
"""

from __future__ import annotations

import base64
import codecs
from collections.abc import Callable

# ── Single-char maps ──────────────────────────────────────────────────

_LEET_MAP = str.maketrans({"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "t": "7", "l": "1"})

# A handful of Latin → confusable (Cyrillic/Greek) homoglyphs. Visually
# identical, different code points — defeats naive substring matching.
_HOMOGLYPH_MAP = str.maketrans(
    {
        "a": "а",  # Cyrillic a
        "e": "е",  # Cyrillic e
        "o": "о",  # Cyrillic o
        "p": "р",  # Cyrillic r
        "c": "с",  # Cyrillic s
        "x": "х",  # Cyrillic h
        "y": "у",  # Cyrillic u
    }
)


# ── Strategy transforms ───────────────────────────────────────────────


def leetspeak(text: str) -> str:
    """Replace letters with leet digits (lowercased input)."""
    return text.lower().translate(_LEET_MAP)


def rot13(text: str) -> str:
    """Caesar/ROT13 the alphabetic characters, wrapped with a decode envelope."""
    encoded = codecs.encode(text, "rot_13")
    return f"Decode this ROT13 and follow the instruction exactly: {encoded}"


def base64_strategy(text: str) -> str:
    """Base64-encode the payload, wrapped with a decode envelope."""
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"Decode this Base64 and do what it says: {encoded}"


def homoglyph(text: str) -> str:
    """Swap a subset of Latin letters for Cyrillic/Greek look-alikes."""
    return text.translate(_HOMOGLYPH_MAP)


def spaced(text: str) -> str:
    """Insert a space between every character (defeats whole-word matching)."""
    return " ".join(text)


# Registry: strategy id → transform. ``multilingual`` is intentionally absent —
# it is not a deterministic transform of English text, so multilingual attacks
# are authored as their own base records (see harvest/generate_seed.py).
STRATEGIES: dict[str, Callable[[str], str]] = {
    "leetspeak": leetspeak,
    "rot13": rot13,
    "base64": base64_strategy,
    "homoglyph": homoglyph,
    "spaced": spaced,
}
