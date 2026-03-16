"""Generate BENCHMARK.md from JSON results + machine info.

Usage:
    cd apps/proxy-service
    python -m benchmarks.generate_report
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from benchmarks.common import collect_machine_info

RESULTS_DIR = Path(__file__).parent / "results"
OUTPUT_MD = Path(__file__).resolve().parents[3] / "BENCHMARK.md"
OUTPUT_JSON = RESULTS_DIR / "benchmark_full.json"


def load(name: str) -> dict | list | None:
    path = RESULTS_DIR / name
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def generate() -> str:
    security = load("security.json")
    latency = load("latency.json")
    memory = load("memory.json")
    e2e = load("e2e.json")
    machine = collect_machine_info()
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = []

    # ── Header ────────────────────────────────────────────────────
    lines.extend(
        [
            "# AI Protector — Benchmark Results",
            "",
        ]
    )

    # ── Summary table (the hook) ──────────────────────────────────
    lines.extend(
        [
            "## Summary",
            "",
        ]
    )

    summary_rows: list[tuple[str, str]] = []

    # Security metrics
    if security:
        balanced = next((r for r in security if r["policy"] == "balanced"), security[0])
        attacks_total = balanced["true_positive"] + balanced["false_negative"]
        summary_rows.append(
            (
                "Attack detection rate",
                f"**{balanced['detection_rate']:.1f}%** ({balanced['true_positive']}/{attacks_total} attacks blocked)",
            )
        )
        summary_rows.append(
            ("False positive rate", f"**{balanced['false_positive_rate']:.1f}%** (safe prompts incorrectly blocked)")
        )
        summary_rows.append(("Attack scenarios tested", f"{balanced['total']}"))
        summary_rows.append(
            (
                "Attack categories",
                f"{len([c for c, s in balanced['categories'].items() if s.get('is_attack_category', True)])}",
            )
        )

    # Latency metrics
    if latency:
        balanced_lat = [r for r in latency if r["policy"] == "balanced"]
        if balanced_lat:
            p50s = [r["total"]["p50"] for r in balanced_lat]
            avg_p50 = sum(p50s) / len(p50s)
            summary_rows.append(("Pre-LLM pipeline overhead (p50)", f"**{avg_p50:.0f} ms**"))

    # E2E metrics
    if e2e:
        allow = e2e.get("allow_path", {})
        overhead_pct = allow.get("overhead_pct", {})
        overhead_ms = allow.get("overhead_ms", {})
        if overhead_pct and overhead_ms:
            summary_rows.append(
                (
                    "End-to-end overhead vs direct LLM",
                    f"**{overhead_ms.get('p50', '?')} ms** ({overhead_pct.get('p50', '?'):.1f}%)",
                )
            )
        block = e2e.get("block_path", {})
        resp_time = block.get("response_time", {})
        if resp_time:
            summary_rows.append(("Attack rejection time (p50)", f"**{resp_time.get('p50', '?')} ms**"))

    # Memory
    if memory:
        total = next((r for r in memory if "TOTAL" in r["component"]), None)
        if total:
            summary_rows.append(("Memory (all scanners loaded)", f"**{total['delta_mb']:.0f} MB**"))

    summary_rows.append(("Policy tested", "balanced (default)"))
    summary_rows.append(("Deterministic", "Yes — no LLM-as-judge, rules + ML scanners"))

    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    for label, value in summary_rows:
        lines.append(f"| {label} | {value} |")
    lines.append("")

    # ── Machine info ──────────────────────────────────────────────
    lines.extend(
        [
            "## Test Environment",
            "",
            "| | |",
            "|---|---|",
            f"| OS | {machine['os']} ({machine['arch']}) |",
            f"| CPU | {machine['cpu']} |",
            f"| Cores | {machine['cpu_cores_physical']} physical / {machine['cpu_cores_logical']} logical |",
            f"| RAM | {machine['ram_total_gb']} GB |",
            f"| Python | {machine['python']} |",
            f"| Runtime | {machine['runtime']} |",
            f"| Date | {ts} |",
            "",
        ]
    )

    # ── Security detection ────────────────────────────────────────
    if security:
        lines.extend(
            [
                "## Security Detection Rate",
                "",
            ]
        )

        # Policy comparison table
        lines.append("| Policy | Scenarios | Detection Rate | False Positive Rate |")
        lines.append("|--------|-----------|----------------|---------------------|")
        for r in security:
            lines.append(
                f"| {r['policy']} | {r['total']} | **{r['detection_rate']:.1f}%** | {r['false_positive_rate']:.1f}% |"
            )
        lines.append("")

        # Per-category breakdown for balanced
        balanced = next((r for r in security if r["policy"] == "balanced"), security[0])
        lines.extend(
            [
                f"### Per-Category Breakdown ({balanced['policy']} policy)",
                "",
                "| Category | Scenarios | Detected | Rate |",
                "|----------|-----------|----------|------|",
            ]
        )
        for cat, stats in sorted(balanced["categories"].items()):
            is_attack = stats.get("is_attack_category", True)
            rate = stats["detected"] / stats["total"] * 100 if stats["total"] > 0 else 0

            if is_attack:
                marker = "🟢" if rate == 100 else "🟡" if rate >= 80 else "🔴"
            else:
                # Safe categories: "detected" means correctly allowed
                marker = "🟢" if rate == 100 else "🔴"
            lines.append(f"| {marker} {cat} | {stats['total']} | {stats['detected']} | {rate:.0f}% |")
        lines.append("")

        # Missed attacks
        missed = balanced.get("missed_sample", [])
        if missed:
            lines.extend(
                [
                    "<details>",
                    f"<summary>Missed attacks ({len(missed)} scenarios — obfuscation, encoding, hallucination)</summary>",
                    "",
                    "| ID | Category | Intent | Risk | Prompt |",
                    "|----|----------|--------|------|--------|",
                ]
            )
            for m in missed:
                prompt = m["prompt"][:100].replace("|", "\\|").replace("\n", " ")
                lines.append(f"| {m['id']} | {m['category']} | {m['intent']} | {m['risk']:.2f} | {prompt} |")
            lines.extend(["", "</details>", ""])

    # ── End-to-end overhead ───────────────────────────────────────
    if e2e:
        lines.extend(
            [
                "## End-to-End Overhead",
                "",
                f"Real LLM calls through the proxy vs direct. Model: `{e2e['model']}`.",
                "",
                "> **Note**: End-to-end overhead includes Docker networking round-trip (~290 ms).",
                "> The actual security pipeline adds **~50 ms** of CPU processing (see Pipeline",
                "> Latency Breakdown below). In a sidecar or same-host deployment, overhead",
                "> approaches the standalone pipeline figure.",
                "",
            ]
        )

        allow = e2e.get("allow_path", {})
        if allow.get("samples"):
            d = allow["direct_llm"]
            p = allow["through_proxy"]
            o = allow["overhead_ms"]
            op = allow["overhead_pct"]
            lines.extend(
                [
                    "### ALLOW Path (safe prompts)",
                    "",
                    "| Metric | p50 | p95 | Mean |",
                    "|--------|-----|-----|------|",
                    f"| Direct LLM call | {d['p50']:.0f} ms | {d['p95']:.0f} ms | {d['mean']:.0f} ms |",
                    f"| Through proxy | {p['p50']:.0f} ms | {p['p95']:.0f} ms | {p['mean']:.0f} ms |",
                    f"| **Overhead** | **{o['p50']:+.0f} ms** | **{o['p95']:+.0f} ms** | **{o['mean']:+.0f} ms** |",
                    f"| **Overhead %** | **{op['p50']:+.1f}%** | **{op['p95']:+.1f}%** | **{op['mean']:+.1f}%** |",
                    "",
                ]
            )

        block = e2e.get("block_path", {})
        if block.get("samples"):
            b = block["response_time"]
            lines.extend(
                [
                    "### BLOCK Path (attack prompts)",
                    "",
                    f"Attacks rejected without calling the LLM. "
                    f"{block['blocked_correctly']}/{block['total_attacks']} blocked correctly.",
                    "",
                    "| Metric | p50 | p95 | Mean |",
                    "|--------|-----|-----|------|",
                    f"| Rejection time | {b['p50']:.0f} ms | {b['p95']:.0f} ms | {b['mean']:.0f} ms |",
                    "",
                ]
            )

    # ── Latency per-node ──────────────────────────────────────────
    if latency:
        lines.extend(
            [
                "## Pipeline Latency Breakdown",
                "",
                "Pre-LLM pipeline (parse → intent → rules → scanners → decision). "
                "No LLM call, no network I/O — pure CPU overhead.",
                "",
            ]
        )

        # Group by policy
        by_policy: dict[str, list[dict]] = {}
        for r in latency:
            by_policy.setdefault(r["policy"], []).append(r)

        lines.append("### Per-Policy Total (p50, ms)")
        lines.append("")
        lines.append("| Policy | Safe prompts | Attack prompts | All prompts |")
        lines.append("|--------|-------------|----------------|-------------|")

        for policy, results in by_policy.items():
            safe = [r["total"]["p50"] for r in results if r["prompt_type"].startswith("safe")]
            attack = [r["total"]["p50"] for r in results if r["prompt_type"].startswith("attack")]
            all_p50 = [r["total"]["p50"] for r in results]
            safe_avg = sum(safe) / len(safe) if safe else 0
            attack_avg = sum(attack) / len(attack) if attack else 0
            all_avg = sum(all_p50) / len(all_p50) if all_p50 else 0
            lines.append(f"| {policy} | {safe_avg:.1f} ms | {attack_avg:.1f} ms | {all_avg:.1f} ms |")
        lines.append("")

        # Node breakdown for balanced
        balanced_lat = [r for r in latency if r["policy"] == "balanced"]
        if balanced_lat:
            representative = next(
                (r for r in balanced_lat if r["prompt_type"] == "attack_jailbreak"),
                balanced_lat[0],
            )
            lines.extend(
                [
                    f"### Node Breakdown ({representative['policy']} / {representative['prompt_type']})",
                    "",
                    "| Node | p50 (ms) | p95 (ms) | Mean (ms) | % of total |",
                    "|------|----------|----------|-----------|------------|",
                ]
            )
            total_mean = representative["total"]["mean"]
            for node in ("parse", "intent", "rules", "scanners", "decision"):
                if node in representative["nodes"]:
                    ns = representative["nodes"][node]
                    pct = (ns["mean"] / total_mean * 100) if total_mean > 0 else 0
                    lines.append(f"| {node} | {ns['p50']:.2f} | {ns['p95']:.2f} | {ns['mean']:.2f} | {pct:.0f}% |")
            lines.append("")

    # ── Memory ────────────────────────────────────────────────────
    if memory:
        lines.extend(
            [
                "## Memory Footprint",
                "",
                "| Component | Delta |",
                "|-----------|-------|",
            ]
        )
        for r in memory:
            lines.append(f"| {r['component']} | {r['delta_mb']:+.0f} MB |")
        lines.append("")

    # ── Methodology ───────────────────────────────────────────────
    lines.extend(
        [
            "## Methodology",
            "",
            "- **Security**: Each of the 358 attack scenarios runs through the full pre-LLM pipeline "
            "(parse → intent → rules → scanners → decision) with the specified policy. "
            "Detection = BLOCK or MODIFY when expected. False positive = BLOCK when ALLOW expected.",
            "- **Latency**: Pre-LLM pipeline measured in isolation (no LLM call, no network). "
            "Warmup runs precede measurement. Results show pure CPU overhead the proxy adds.",
            "- **End-to-end**: Same prompts sent directly to the LLM and through the proxy. "
            "Overhead = proxy_time − direct_time.",
            "- **Memory**: RSS measured via `psutil` before/after scanner initialization.",
            "- **Deterministic**: No LLM-as-judge — all decisions use rules, keyword classifiers, "
            "and ML scanners (LLM Guard, NeMo Guardrails, Presidio).",
            "",
            "## Reproduce",
            "",
            "```bash",
            "cd apps/proxy-service",
            "pip install -e '.[dev]'",
            "",
            "# Standalone benchmarks (no Docker needed)",
            "python -m benchmarks.bench_security --all-policies",
            "python -m benchmarks.bench_latency --all-policies --iterations 50",
            "python -m benchmarks.bench_memory",
            "",
            "# End-to-end (requires running proxy + API key)",
            "make demo  # in another terminal",
            "GEMINI_API_KEY=... python -m benchmarks.bench_e2e --iterations 10",
            "",
            "# Generate this report",
            "python -m benchmarks.generate_report",
            "```",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> None:
    report = generate()

    # Write markdown
    OUTPUT_MD.write_text(report)
    print(f"Report: {OUTPUT_MD} ({len(report)} chars)")

    # Write full JSON (all results + machine info combined)
    machine = collect_machine_info()
    full = {
        "generated": datetime.now(UTC).isoformat(),
        "machine": machine,
        "security": load("security.json"),
        "latency": load("latency.json"),
        "memory": load("memory.json"),
        "e2e": load("e2e.json"),
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(full, indent=2))
    print(f"JSON:   {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
