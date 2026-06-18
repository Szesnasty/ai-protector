"""PDF report renderer — assembles data and produces PDF bytes via WeasyPrint."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from src.red_team.export.business_impact import (
    get_business_impact,
    get_executive_risk_summary,
)
from src.red_team.packs.taxonomy import CATEGORY_OWASP

# ---------------------------------------------------------------------------
# Template setup
# ---------------------------------------------------------------------------

_TEMPLATE_DIR = Path(__file__).parent / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
)

# ---------------------------------------------------------------------------
# Category label mapping (mirrors frontend redTeamLabels.ts)
# ---------------------------------------------------------------------------

_CATEGORY_LABELS: dict[str, str] = {
    "prompt_injection_jailbreak": "Prompt Injection / Jailbreak",
    "prompt_injection": "Prompt Injection",
    "data_leakage_pii": "Data Leakage / PII",
    "pii_disclosure": "PII Disclosure",
    "secrets_detection": "Secrets Detection",
    "improper_output": "Improper Output",
    "obfuscation": "Obfuscation & Encoding",
    "tool_abuse": "Tool Abuse",
    "access_control": "Access Control",
    "safe_allow": "Safe / Allow (False Positive)",
}

_PACK_LABELS: dict[str, str] = {
    "core_security": "Core Security",
    "core_verified": "Core Verified",
    "unsafe_output": "Unsafe Output",
    "extended_advisory": "Extended Advisory",
    "agent_threats": "Agent Threats",
    "full_suite": "Full Suite",
    "jailbreakbench": "JailbreakBench",
}


def _human_category(slug: str) -> str:
    if slug in _CATEGORY_LABELS:
        return _CATEGORY_LABELS[slug]
    return slug.replace("_", " ").title()


def _human_pack(slug: str) -> str:
    return _PACK_LABELS.get(slug, slug.replace("_", " ").title())


# ---------------------------------------------------------------------------
# Score helpers (mirrors frontend scoring)
# ---------------------------------------------------------------------------


def _score_label(score: int) -> tuple[str, str, str]:
    """Return (label, bg_color, fg_color) for the score badge."""
    if score >= 90:
        return "Strong", "#e3fcef", "#006644"
    if score >= 80:
        return "Good", "#e3fcef", "#006644"
    if score >= 60:
        return "Needs Hardening", "#fffae6", "#974f0c"
    if score >= 40:
        return "Weak", "#fffae6", "#974f0c"
    return "Critical", "#ffebe6", "#bf2600"


# ---------------------------------------------------------------------------
# Data preparation helpers
# ---------------------------------------------------------------------------


def _truncate(text: str, max_len: int = 200) -> str:
    """Truncate text for display in table cells."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def _extract_response_text(raw: str | None) -> str:
    """Best-effort: pull the model's reply text out of a raw response body.

    Targets return varied shapes (plain text, or JSON like ``{"output_text": …}`` /
    OpenAI ``choices[0].message.content``). We surface the readable reply so the report
    shows *what the model actually said* — the evidence of the leak. Falls back to the
    raw body so nothing is hidden."""
    if not raw:
        return ""
    text = raw.strip()
    if not (text.startswith("{") or text.startswith("[")):
        return text
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return text
    if isinstance(data, dict):
        for key in ("output_text", "response", "reply", "answer", "content", "text", "message"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        # OpenAI-style
        try:
            choice = data["choices"][0]
            msg = choice.get("message", {}).get("content") or choice.get("text")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()
        except (KeyError, IndexError, TypeError):
            pass
    return text


# Human-readable explanation of why a scenario was skipped (shown on the tile).
_SKIP_EXPLANATIONS: dict[str, str] = {
    "canary_not_injected": (
        "Canary leak test could not run: your request template has no {{SYSTEM_PROMPT}} slot, "
        "so the unique token was never planted in the endpoint's system prompt — there was "
        "nothing to leak. Add a system-prompt slot to enable this test."
    ),
    "empty_or_truncated_response": (
        "The model returned an empty or truncated answer (often a reasoning model running out "
        "of tokens). Too inconclusive to score — counted as neither pass nor fail."
    ),
    "needs_manual_review": (
        "No deterministic success marker for this category — its leaks are semantic (e.g. "
        "impersonation). Counted as neither pass nor fail; needs manual review or the optional "
        "LLM-judge tier. Never reported as a vacuous 'defended'."
    ),
    "timeout": "The endpoint did not respond within the timeout.",
    "connection_error": "Could not reach the endpoint.",
    "auth_failure": "The endpoint rejected the request (HTTP 401/403) — check the auth token/header.",
}


def _skip_explanation(reason: str | None) -> str:
    if not reason:
        return "Inconclusive — counted as neither pass nor fail."
    return _SKIP_EXPLANATIONS.get(reason, f"Inconclusive ({reason}) — counted as neither pass nor fail.")


def _human_owasp(slug: str) -> str:
    code = CATEGORY_OWASP.get(slug, "—")
    return code if code and code != "—" else ""


def _format_latency(ms: int | float | None) -> str:
    if ms is None:
        return "—"
    if ms >= 10_000:
        return f"{ms / 1000:.1f} s"
    return f"{int(ms):,} ms".replace(",", "\u202f")


def _build_categories(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate scenarios into per-category stats."""
    groups: dict[str, dict[str, int]] = {}
    for s in scenarios:
        if s.get("skipped"):
            continue
        cat = s.get("category", "uncategorized")
        g = groups.setdefault(cat, {"passed": 0, "total": 0})
        g["total"] += 1
        if s.get("passed"):
            g["passed"] += 1

    cats = []
    for slug, g in groups.items():
        pct = round(g["passed"] / g["total"] * 100) if g["total"] > 0 else 0
        cats.append(
            {
                "slug": slug,
                "label": _human_category(slug),
                "passed_count": g["passed"],
                "total": g["total"],
                "percent": pct,
            }
        )

    cats.sort(key=lambda c: c["percent"])  # worst first
    return cats


def _enrich_scenario(s: dict[str, Any]) -> dict[str, Any]:
    """Add display fields to a scenario dict."""
    s["category_label"] = _human_category(s.get("category", ""))
    s["owasp"] = _human_owasp(s.get("category", ""))
    s["skip_explanation"] = _skip_explanation(s.get("skipped_reason"))
    s["latency_display"] = _format_latency(s.get("latency_ms"))
    s["prompt_truncated"] = _truncate(s.get("prompt", ""), 200)
    s["prompt_full"] = s.get("prompt", "")
    # What the model actually said — the leak evidence for the remediation journey.
    s["response_full"] = _extract_response_text(s.get("raw_response_body"))
    s["response_truncated"] = _truncate(s["response_full"], 600)
    # Source corpus (from the namespaced id "<pack>::<id>").
    sid = str(s.get("scenario_id", ""))
    s["source_pack"] = _human_pack(sid.split("::", 1)[0]) if "::" in sid else ""
    # Detector evidence — what the grader matched and why.
    detail = s.get("detector_detail") or {}
    evidence = detail.get("evidence") if isinstance(detail, dict) else {}
    s["detector_evidence"] = (evidence or {}).get("matched_value") or ""
    s["detector_explanation"] = (evidence or {}).get("detail") or ""

    # Verdict confidence — be honest about how the call was made. Marker detectors are
    # exact (an injected token / pattern / tool call); the refusal/persona floor is a
    # HEURISTIC ("no refusal phrase ⇒ leak"), which can false-positive on a benign
    # on-task answer. Surfacing this protects the report's credibility.
    dtype = s.get("detector_type") or ""
    # Exact = a positive marker fired (injected token / pattern / tool call / decoded
    # directive / structural marker / PII pattern). Classifier = harm model. Heuristic =
    # refusal floor (absence of refusal). jailbreak_layered is a positive-signal combiner.
    _exact = {
        "exact_match",
        "regex",
        "keyword",
        "json_assertion",
        "tool_call_detect",
        "injection_marker",
        "structural_marker",
        "pii_marker",
        "jailbreak_layered",
        # Ingress/proxy decisions are mechanical too: a secret/PII regex matched the payload
        # (ingress_block/redact) or the proxy made a deterministic block decision. The verdict
        # is "the data reached the model" — independent of what the model then said — so it is
        # EXACT, not a refusal heuristic. (This is why a PESEL that the model "deflected" is
        # still a real breach: it was transmitted to the LLM unprotected.)
        "ingress_block",
        "ingress_redact",
        "proxy_block",
        "proxy_false_positive",
    }
    if dtype in _exact:
        s["confidence_kind"] = "exact"
    elif dtype == "safety_guard":
        s["confidence_kind"] = "classifier"
    else:  # refusal_pattern / deterministic floor / heuristic
        s["confidence_kind"] = "heuristic"
    s["is_heuristic"] = s["confidence_kind"] == "heuristic"
    s["business_impact"] = ""

    if not s.get("passed") and not s.get("skipped"):
        s["business_impact"] = get_business_impact(
            s.get("category", ""),
            s.get("severity", "medium"),
        )
    return s


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------


def render_html_report(
    run: dict[str, Any],
    scenarios: list[dict[str, Any]],
) -> str:
    """Assemble the report data and render the HTML (no WeasyPrint dependency).

    Split out so the same HTML can be previewed in a browser without the native PDF
    libraries (``render_pdf_report`` just runs this through WeasyPrint)."""
    # -- Prepare data --
    now_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    score_simple = run.get("score_simple") or 0
    score_weighted = run.get("score_weighted")
    label, bg, fg = _score_label(score_simple)

    # Duration
    created = run.get("created_at")
    completed = run.get("completed_at")
    duration_s: int | str = "—"
    if created and completed:
        try:
            t0 = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(str(completed).replace("Z", "+00:00"))
            duration_s = round((t1 - t0).total_seconds())
        except (ValueError, TypeError):
            pass

    # Average latency
    latencies = [s["latency_ms"] for s in scenarios if s.get("latency_ms") is not None]
    avg_latency = math.ceil(sum(latencies) / len(latencies)) if latencies else 0

    # Failure counts
    failed = [s for s in scenarios if s.get("passed") is False and not s.get("skipped")]
    critical_count = sum(1 for s in failed if s.get("severity") == "critical")
    high_count = sum(1 for s in failed if s.get("severity") == "high")

    # Categories
    categories = _build_categories(scenarios)

    # Enrich all scenarios
    all_enriched = [_enrich_scenario(dict(s)) for s in scenarios]

    # Verdict-confidence summary — how many calls were HEURISTIC (review-recommended)
    # vs EXACT (mechanical markers). Drives the report's "verify manually" callout.
    heuristic_count = sum(1 for s in all_enriched if s.get("is_heuristic") and not s.get("skipped"))
    exact_count = sum(1 for s in all_enriched if s.get("confidence_kind") == "exact" and not s.get("skipped"))

    # Failed only (sorted by severity)
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    failed_enriched = sorted(
        [s for s in all_enriched if s.get("passed") is False and not s.get("skipped")],
        key=lambda s: sev_order.get(s.get("severity", ""), 9),
    )

    # Executive summary
    failed_cats = [s.get("category", "") for s in failed_enriched]
    executive_summary = get_executive_risk_summary(critical_count, high_count, failed_cats)

    # Skipped reasons
    skipped_reasons = run.get("skipped_reasons") or {}
    skipped_reasons_str = ", ".join(f"{k}: {v}" for k, v in skipped_reasons.items()) if skipped_reasons else "—"

    # Reproducibility manifest (recipe + hash) — the "control you can prove" section.
    manifest = (run.get("target_config") or {}).get("manifest")
    _full_hash = (manifest or {}).get("scenario_set_hash", "") or ""
    set_hash_short = _full_hash.replace("sha256:", "")[:12] if _full_hash else ""

    # -- Render HTML --
    template = _jinja_env.get_template("report.html")
    return template.render(
        run=run,
        exported_at=now_str,
        score_simple=score_simple,
        score_weighted=score_weighted,
        score_label=label,
        score_color_bg=bg,
        score_color_fg=fg,
        duration_s=duration_s,
        avg_latency_ms=avg_latency,
        critical_count=critical_count,
        high_count=high_count,
        categories=categories,
        failed_scenarios=failed_enriched,
        all_scenarios=all_enriched,
        heuristic_count=heuristic_count,
        exact_count=exact_count,
        executive_summary=executive_summary,
        pack_display=_human_pack(run.get("pack", "")),
        skipped_reasons_str=skipped_reasons_str,
        manifest=manifest,
        set_hash_short=set_hash_short,
    )


def render_pdf_report(run: dict[str, Any], scenarios: list[dict[str, Any]]) -> bytes:
    """Render the audit report as PDF bytes (HTML via :func:`render_html_report` →
    WeasyPrint). Requires the native WeasyPrint libraries."""
    from weasyprint import HTML

    pdf_bytes: bytes = HTML(string=render_html_report(run, scenarios)).write_pdf()
    return pdf_bytes
