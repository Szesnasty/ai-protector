"""Deobfuscation / normalization for detection (A2).

Builds a *scan text* = the raw user message plus decoded/normalized variants of
common obfuscations (leetspeak, spaced characters, homoglyphs, ROT13, base64).

Only the **detection** path reads this. The original message is still what gets
forwarded to the LLM, and PII detection (Presidio) keeps running on the raw text
so entity offsets stay valid. The injection-oriented detectors (intent keyword
classifier, denylist, LLM Guard) read the scan text so an obfuscated attack is
decoded back into something they recognize.

All transforms are deterministic and dependency-free. Every transform is wrapped
defensively — a decoding error must never break the pipeline.
"""

from __future__ import annotations

import base64
import binascii
import codecs
import re
import unicodedata

# Skip very large inputs — decoding many MB would be a DoS vector.
MAX_SCAN_LEN = 8_000

# Leet → letter. '1' is ambiguous (i or l) so both variants are produced.
_LEET_BASE = {
    "0": "o",
    "3": "e",
    "4": "a",
    "5": "s",
    "6": "g",
    "7": "t",
    "8": "b",
    "9": "g",
    "@": "a",
    "$": "s",
}

# Cyrillic / Greek look-alikes → Latin (reverse of common homoglyph attacks).
_HOMOGLYPH_MAP = str.maketrans(
    {
        "а": "a",
        "е": "e",
        "о": "o",
        "р": "p",
        "с": "c",
        "х": "x",
        "у": "y",
        "ѕ": "s",
        "і": "i",
        "ј": "j",
        "ԁ": "d",
        "ո": "n",
        "м": "m",
        "т": "t",
        "к": "k",
        "ν": "v",
        "ο": "o",
        "ρ": "p",
        "α": "a",
        "ε": "e",
        # NOTE: this is the common-confusables set, not exhaustive. Expanding it
        # naively with more Cyrillic/Greek look-alikes was measured to LOWER
        # homoglyph detection (99.5% → 82%) — some additions mis-fold promptfoo's
        # chosen confusables. Vet any new mapping against the homoglyph benchmark.
    }
)

_ZERO_WIDTH = re.compile(r"[​-‏‪-‮⁠﻿]")
_B64_RE = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")
_LEET_TRIGGER = re.compile(r"[A-Za-z][0-9@$]|[0-9@$][A-Za-z]")

# Common English words — used to tell "looks like English" from "looks encoded".
_COMMON_WORDS = frozenset(
    [
        "the",
        "be",
        "to",
        "of",
        "and",
        "a",
        "in",
        "that",
        "have",
        "it",
        "for",
        "not",
        "on",
        "with",
        "he",
        "as",
        "you",
        "do",
        "at",
        "this",
        "but",
        "his",
        "by",
        "from",
        "they",
        "we",
        "say",
        "her",
        "she",
        "or",
        "an",
        "will",
        "my",
        "one",
        "all",
        "would",
        "there",
        "their",
        "what",
        "is",
        "are",
        "how",
        "can",
        "your",
        "please",
        "i",
        "me",
        "give",
        "show",
        "tell",
        "write",
        "status",
        "order",
        "help",
        "find",
        "about",
    ]
)
# ROT13 is only attempted when raw text scores below this and the decoded text
# scores above it — otherwise benign English would be decoded into injection-like
# gibberish (a false-positive source).
_ENGLISH_THRESHOLD = 0.15


def _english_score(text: str) -> float:
    words = re.findall(r"[a-z]+", text.lower())
    if not words:
        return 0.0
    return sum(1 for w in words if w in _COMMON_WORDS) / len(words)


def _leet_decode(text: str, one_as: str) -> str:
    table = dict(_LEET_BASE)
    table["1"] = one_as
    return "".join(table.get(ch, ch) for ch in text)


def _strip_zero_width(text: str) -> str:
    return _ZERO_WIDTH.sub("", text)


def _fold_homoglyphs(text: str) -> str:
    return unicodedata.normalize("NFKC", text).translate(_HOMOGLYPH_MAP)


def _collapse_spaced(text: str) -> str:
    """Join 'h e l l o' → 'hello' when most tokens are single characters."""
    tokens = text.split()
    if len(tokens) >= 4 and sum(1 for t in tokens if len(t) == 1) / len(tokens) > 0.6:
        return re.sub(r"\s+", "", text)
    return text


def _looks_texty(s: str) -> bool:
    """True when ``s`` looks like natural-language text (not random bytes)."""
    if len(s) < 4:
        return False
    printable = sum(1 for c in s if c.isprintable())
    letters = sum(1 for c in s if c.isalpha())
    return printable / len(s) > 0.85 and letters >= max(3, int(len(s) * 0.4))


def _rot13(text: str) -> str:
    try:
        return codecs.decode(text, "rot_13")
    except Exception:
        return text


def _b64_variants(text: str) -> list[str]:
    out: list[str] = []
    for match in _B64_RE.finditer(text):
        tok = match.group()
        try:
            dec = base64.b64decode(tok + "=" * (-len(tok) % 4), validate=False).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        if _looks_texty(dec):
            out.append(dec)
    return out


def build_scan_text(raw: str) -> str:
    """Return ``raw`` plus any meaningfully different decoded variants.

    The original text is always kept first so nothing is lost; variants are
    appended only when they differ from the raw text. Safe to call on any
    input — never raises.
    """
    if not raw or len(raw) > MAX_SCAN_LEN:
        return raw

    try:
        cleaned = _strip_zero_width(raw)
        variants: list[str] = []

        if cleaned != raw:
            variants.append(cleaned)

        # Leetspeak — only when digits/symbols are glued to letters.
        if _LEET_TRIGGER.search(cleaned):
            for one in ("i", "l"):
                variants.append(_leet_decode(cleaned, one))

        spaced = _collapse_spaced(cleaned)
        if spaced != cleaned:
            variants.append(spaced)

        homoglyph = _fold_homoglyphs(cleaned)
        if homoglyph != cleaned:
            variants.append(homoglyph)

        # ROT13: only when the raw text does NOT look like English (i.e. it may
        # be encoded) and decoding turns it INTO English. This avoids decoding a
        # benign English prompt into injection-like gibberish.
        if _english_score(cleaned) < _ENGLISH_THRESHOLD:
            rot = _rot13(cleaned)
            if rot != cleaned and _looks_texty(rot) and _english_score(rot) >= _ENGLISH_THRESHOLD:
                variants.append(rot)

        variants.extend(_b64_variants(cleaned))

        # Dedupe; drop anything equal to the raw text.
        raw_key = raw.strip().lower()
        seen: set[str] = set()
        uniq: list[str] = []
        for v in variants:
            key = v.strip().lower()
            if not key or key == raw_key or key in seen:
                continue
            seen.add(key)
            uniq.append(v)

        if not uniq:
            return raw
        # Raw first, then decoded variants. (Variants-first was measured to LOWER
        # obfuscation detection ~13 pp — the combined raw+decoded signal scores
        # best with the obfuscated form leading.) Residual: a very long benign
        # prefix can push a short obfuscated suffix past the ~512-token model
        # window — an inherent limitation of all the ML scanners, not just A2.
        return raw + "\n" + "\n".join(uniq)
    except Exception:
        # Detection must never be broken by a decoding edge case.
        return raw
