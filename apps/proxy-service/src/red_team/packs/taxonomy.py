"""Build-time mapping: a source's NATIVE category label → a canonical `Category`.

The unified taxonomy IS the `Category` enum (schemas/enums.py) — the single source
of truth. This module maps each external source's native label onto a valid
`Category` value (used when GENERATING packs), and extracts the native subtype for
the scenario's `subcategory` drill-down field.

At runtime nothing maps: scenario.category is already a canonical `Category`, and
scenario.subcategory carries the source granularity (e.g. "cybercrime_intrusion").
"""

from __future__ import annotations

from src.red_team.schemas.enums import Category

# Native source family/label → canonical Category value.
# New-source families first; existing Category values map to themselves so
# already-canonical packs pass through `to_category()` unchanged.
NATIVE_TO_CATEGORY: dict[str, str] = {
    # external-source families
    "harmful": Category.HARMFUL_CONTENT.value,
    "pii": Category.PII_DISCLOSURE.value,
    "hijacking": Category.PROMPT_INJECTION.value,
    "imitation": Category.IMPERSONATION.value,
    "overreliance": Category.MISINFORMATION.value,
    "prompt-extraction": Category.SYSTEM_PROMPT_LEAK.value,
    "prompt_extraction": Category.SYSTEM_PROMPT_LEAK.value,
    "ascii-smuggling": Category.OBFUSCATION.value,
    "jailbreak": Category.PROMPT_INJECTION_JAILBREAK.value,
    "indirect": Category.INDIRECT_INJECTION.value,
    # canonical Category values → identity
    **{c.value: c.value for c in Category},
}

# OWASP LLM Top-10 anchor per canonical category (for UI / reporting).
CATEGORY_OWASP: dict[str, str] = {
    Category.PROMPT_INJECTION.value: "LLM01",
    Category.PROMPT_INJECTION_JAILBREAK.value: "LLM01",
    Category.INDIRECT_INJECTION.value: "LLM01",
    Category.OBFUSCATION.value: "LLM01",
    Category.BUSINESS_LOGIC_OVERRIDE.value: "LLM01",
    Category.PII_DISCLOSURE.value: "LLM02",
    Category.DATA_LEAKAGE_PII.value: "LLM02",
    Category.SECRETS_DETECTION.value: "LLM02",
    Category.SYSTEM_PROMPT_LEAK.value: "LLM07",
    Category.IMPROPER_OUTPUT.value: "LLM05",
    Category.UNSAFE_OUTPUT_ARTIFACT.value: "LLM05",
    Category.TOOL_ABUSE.value: "LLM06",
    Category.ACCESS_CONTROL.value: "LLM06",
    Category.MISINFORMATION.value: "LLM09",
    Category.HARMFUL_CONTENT.value: "—",
    Category.IMPERSONATION.value: "—",
    Category.SAFE_ALLOW.value: "—",
}

# Sanity: every mapping target is a real Category value.
assert set(NATIVE_TO_CATEGORY.values()) <= {c.value for c in Category}


def to_category(native: str | None) -> str:
    """Map a native label (possibly 'family:subtype') to a canonical Category value."""
    key = (native or "").strip().lower()
    if key in NATIVE_TO_CATEGORY:
        return NATIVE_TO_CATEGORY[key]
    for sep in (":", "/"):
        if sep in key:
            family = key.split(sep, 1)[0].strip()
            if family in NATIVE_TO_CATEGORY:
                return NATIVE_TO_CATEGORY[family]
    return Category.PROMPT_INJECTION.value  # safe fallback; add unknowns to the map


def subcategory(native: str | None) -> str | None:
    """Native subtype for drill-down: part after 'family:' if namespaced, else the
    native label itself; None if empty."""
    key = (native or "").strip()
    if not key:
        return None
    for sep in (":", "/"):
        if sep in key:
            return key.split(sep, 1)[1].strip() or None
    return key
