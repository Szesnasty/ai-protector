"""PDF report renderer — assembles data and produces PDF bytes via WeasyPrint."""

from __future__ import annotations

import html
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from src.red_team.export.business_impact import (
    get_business_impact,
    get_executive_risk_summary,
)

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
        cats.append({
            "slug": slug,
            "label": _human_category(slug),
            "passed_count": g["passed"],
            "total": g["total"],
            "percent": pct,
        })

    cats.sort(key=lambda c: c["percent"])  # worst first
    return cats


def _enrich_scenario(s: dict[str, Any]) -> dict[str, Any]:
    """Add display fields to a scenario dict."""
    s["category_label"] = _human_category(s.get("category", ""))
    s["latency_display"] = _format_latency(s.get("latency_ms"))
    s["prompt_truncated"] = _truncate(s.get("prompt", ""), 200)
    s["prompt_full"] = s.get("prompt", "")
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


def render_pdf_report(
    run: dict[str, Any],
    scenarios: list[dict[str, Any]],
) -> bytes:
    """Render a complete PDF audit report.

    Parameters
    ----------
    run:
        Run detail dict (from RunDetailResponse / serialized).
    scenarios:
        List of scenario result dicts (from ScenarioResultResponse / serialized).

    Returns
    -------
    bytes — PDF file content.
    """
    from weasyprint import HTML

    # -- Prepare data --
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

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

    # -- Render HTML --
    template = _jinja_env.get_template("report.html")
    html_content = template.render(
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
        executive_summary=executive_summary,
        pack_display=_human_pack(run.get("pack", "")),
        skipped_reasons_str=skipped_reasons_str,
    )

    # -- Generate PDF --
    pdf_bytes: bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes
