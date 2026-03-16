"""JailbreakBench benchmark — detection rate against the NeurIPS 2024 dataset.

Downloads jailbreak attack prompts from https://github.com/JailbreakBench/artifacts
and runs them through the AI Protector pre-LLM pipeline.

Dataset: 100 harmful behaviors × 4 attack methods × multiple target models.
  - PAIR (black-box, iterative)
  - GCG (white-box, gradient-based adversarial suffixes)
  - JBC (manual, human-crafted)
  - prompt_with_random_search (black-box, random search)

Each prompt is a real jailbreak that successfully bypassed a target model.
AI Protector's job is to catch them BEFORE they reach any model.

Usage:
    cd apps/proxy-service
    python -m benchmarks.bench_jailbreakbench
    python -m benchmarks.bench_jailbreakbench --all-policies
    python -m benchmarks.bench_jailbreakbench --methods PAIR GCG JBC
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path

import httpx

from benchmarks.common import POLICIES, RESULTS_DIR, build_pre_llm_pipeline, collect_machine_info, make_state

ARTIFACTS_BASE = "https://raw.githubusercontent.com/JailbreakBench/artifacts/main/attack-artifacts"

ATTACK_SOURCES: dict[str, list[str]] = {
    "PAIR": [
        "black_box/vicuna-13b-v1.5",
        "black_box/gpt-3.5-turbo-1106",
        "black_box/gpt-4-0125-preview",
    ],
    "GCG": [
        "white_box/vicuna-13b-v1.5",
        "transfer/gpt-3.5-turbo-1106",
        "transfer/gpt-4-0125-preview",
    ],
    "JBC": [
        "manual/vicuna-13b-v1.5",
        "manual/gpt-3.5-turbo-1106",
        "manual/gpt-4-0125-preview",
    ],
    "prompt_with_random_search": [
        "black_box/vicuna-13b-v1.5",
        "black_box/gpt-3.5-turbo-1106",
        "black_box/gpt-4-0125-preview",
    ],
}

JBB_CATEGORIES = [
    "Harassment/Discrimination",
    "Malware/Hacking",
    "Physical harm",
    "Economic harm",
    "Fraud/Deception",
    "Disinformation",
    "Sexual/Adult content",
    "Privacy",
    "Expert advice",
    "Government decision-making",
]

CACHE_DIR = Path(__file__).parent / "datasets" / "jailbreakbench"


# ── Download / cache ──────────────────────────────────────────────────


def download_artifacts(methods: list[str]) -> dict[str, list[dict]]:
    """Download JailbreakBench artifacts, cached locally."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    all_prompts: dict[str, list[dict]] = {}

    for method in methods:
        sources = ATTACK_SOURCES.get(method, [])
        method_prompts: list[dict] = []
        seen_prompts: set[str] = set()

        for source in sources:
            model = source.split("/")[-1]
            cache_file = CACHE_DIR / f"{method}_{model}.json"

            if cache_file.exists():
                with open(cache_file) as f:
                    data = json.load(f)
            else:
                url = f"{ARTIFACTS_BASE}/{method}/{source}.json"
                print(f"  Downloading {url}...")
                resp = httpx.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                cache_file.write_text(json.dumps(data, indent=2))

            for jb in data.get("jailbreaks", []):
                prompt = jb.get("prompt", "")
                if not prompt or prompt in seen_prompts:
                    continue
                seen_prompts.add(prompt)
                method_prompts.append(
                    {
                        "id": f"JBB-{method}-{model}-{jb.get('index', '?')}",
                        "method": method,
                        "target_model": model,
                        "category": jb.get("category", "unknown"),
                        "goal": jb.get("goal", ""),
                        "prompt": prompt,
                        "originally_jailbroken": jb.get("jailbroken", False),
                    }
                )

        all_prompts[method] = method_prompts
        print(f"  {method}: {len(method_prompts)} unique prompts")

    return all_prompts


# ── Benchmark runner ──────────────────────────────────────────────────


@dataclass
class JBBResult:
    method: str
    policy: str
    total: int = 0
    blocked: int = 0
    allowed: int = 0
    by_category: dict[str, dict] = field(default_factory=dict)
    missed: list[dict] = field(default_factory=list)

    @property
    def detection_rate(self) -> float:
        return self.blocked / self.total if self.total > 0 else 0.0

    def record(self, scenario: dict, decision: str, risk_score: float, intent: str) -> None:
        self.total += 1
        cat = scenario["category"]
        if cat not in self.by_category:
            self.by_category[cat] = {"total": 0, "blocked": 0, "allowed": 0}
        self.by_category[cat]["total"] += 1

        if decision in ("BLOCK", "MODIFY"):
            self.blocked += 1
            self.by_category[cat]["blocked"] += 1
        else:
            self.allowed += 1
            self.by_category[cat]["allowed"] += 1
            self.missed.append(
                {
                    "id": scenario["id"],
                    "category": cat,
                    "goal": scenario["goal"][:100],
                    "intent": intent,
                    "risk": risk_score,
                    "prompt_preview": scenario["prompt"][:120],
                }
            )

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "policy": self.policy,
            "total": self.total,
            "blocked": self.blocked,
            "allowed": self.allowed,
            "detection_rate": round(self.detection_rate * 100, 1),
            "by_category": self.by_category,
            "missed_sample": self.missed[:20],
        }


async def run_jbb_benchmark(
    prompts: list[dict],
    method: str,
    policy_name: str,
) -> JBBResult:
    """Run JailbreakBench prompts through the pipeline."""
    pipeline = build_pre_llm_pipeline()
    result = JBBResult(method=method, policy=policy_name)

    # Warmup
    state = make_state("warmup", policy_name)
    await pipeline.ainvoke(state)

    for i, scenario in enumerate(prompts):
        state = make_state(scenario["prompt"], policy_name)
        try:
            out = await pipeline.ainvoke(state)
        except Exception:
            result.record(scenario, "ERROR", 0.0, "error")
            continue

        decision = out.get("decision", "ERROR")
        risk = out.get("risk_score", 0.0)
        intent = out.get("intent", "?")
        result.record(scenario, decision, risk, intent)

        if (i + 1) % 50 == 0:
            print(f"    {i + 1}/{len(prompts)} processed...")

    return result


# ── Output ────────────────────────────────────────────────────────────


def print_results(results: list[JBBResult]) -> None:
    """Print JailbreakBench results."""
    w = 85
    print(f"\n{'=' * w}")
    print("  AI Protector × JailbreakBench (NeurIPS 2024)")
    print(f"{'=' * w}")

    header = f"{'Policy':<10} {'Method':<28} {'Total':>6} {'Blocked':>8} {'Detection':>10}"
    print(header)
    print("-" * len(header))

    for r in results:
        print(f"{r.policy:<10} {r.method:<28} {r.total:>6} {r.blocked:>8} {r.detection_rate * 100:>9.1f}%")

    # Per-category for the first balanced result
    balanced = [r for r in results if r.policy == "balanced"]
    if balanced:
        combined: dict[str, dict] = {}
        for r in balanced:
            for cat, stats in r.by_category.items():
                if cat not in combined:
                    combined[cat] = {"total": 0, "blocked": 0}
                combined[cat]["total"] += stats["total"]
                combined[cat]["blocked"] += stats["blocked"]

        print("\n  Per-category (balanced, all methods combined):")
        print(f"  {'Category':<30} {'Total':>6} {'Blocked':>8} {'Rate':>7}")
        print(f"  {'-' * 55}")
        for cat in JBB_CATEGORIES:
            if cat in combined:
                s = combined[cat]
                rate = s["blocked"] / s["total"] * 100 if s["total"] > 0 else 0
                emoji = "🟢" if rate >= 90 else "🟡" if rate >= 70 else "🔴"
                print(f"  {emoji} {cat:<28} {s['total']:>6} {s['blocked']:>8} {rate:>6.1f}%")

    # Missed sample
    for r in results:
        if r.missed and r.policy == "balanced":
            print(f"\n  Missed attacks ({r.method}, balanced) — {len(r.missed)} shown:")
            for m in r.missed[:5]:
                print(f"    [{m['id']}] {m['category']}: intent={m['intent']}, risk={m['risk']:.2f}")
                print(f"      Goal: {m['goal']}")

    print()


def generate_jbb_report(results: list[dict], machine: dict) -> str:
    """Generate BENCHMARK_JAILBREAKBENCH.md."""
    from datetime import datetime

    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []

    lines.extend(
        [
            "# AI Protector — Pre-LLM Detection Results on JailbreakBench",
            "",
            "> External validation against published jailbreak artifacts from",
            "> [JailbreakBench](https://jailbreakbench.github.io/) (NeurIPS 2024 Datasets & Benchmarks Track).",
            "",
        ]
    )

    # Summary
    balanced_results = [r for r in results if r["policy"] == "balanced"]
    if balanced_results:
        total_prompts = sum(r["total"] for r in balanced_results)
        total_blocked = sum(r["blocked"] for r in balanced_results)
        overall_rate = total_blocked / total_prompts * 100 if total_prompts > 0 else 0

        lines.extend(
            [
                "## Summary",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Overall pre-LLM detection rate | **{overall_rate:.1f}%** |",
                f"| Jailbreak prompts tested | {total_prompts} |",
                f"| Attack methods | {len(balanced_results)} (PAIR, GCG, JBC, Random Search) |",
                f"| Harm categories | {len(JBB_CATEGORIES)} |",
                "| Policy | balanced (default) |",
                "| Benchmark scope | **Pre-LLM pipeline only** |",
                "| LLM call required | No |",
                "| Provider/model response evaluation | No |",
                "",
            ]
        )

    # Per-method table
    lines.extend(
        [
            "## Detection by Attack Method",
            "",
            "| Method | Type | Prompts | Detected | Rate |",
            "|--------|------|---------|----------|------|",
        ]
    )

    method_types = {
        "PAIR": "Black-box, iterative",
        "GCG": "White-box, gradient-based",
        "JBC": "Manual, human-crafted",
        "prompt_with_random_search": "Black-box, random search",
    }

    for r in results:
        if r["policy"] != "balanced":
            continue
        mtype = method_types.get(r["method"], "?")
        rate = r["detection_rate"]
        emoji = "🟢" if rate >= 90 else "🟡" if rate >= 70 else "🔴"
        lines.append(f"| {emoji} {r['method']} | {mtype} | {r['total']} | {r['blocked']} | **{rate:.1f}%** |")
    lines.append("")

    # Per-category (combined from balanced)
    if balanced_results:
        combined: dict[str, dict] = {}
        for r in balanced_results:
            for cat, stats in r["by_category"].items():
                if cat not in combined:
                    combined[cat] = {"total": 0, "blocked": 0}
                combined[cat]["total"] += stats["total"]
                combined[cat]["blocked"] += stats["blocked"]

        lines.extend(
            [
                "## Detection by Harm Category",
                "",
                "| Category | Prompts | Detected | Rate |",
                "|----------|---------|----------|------|",
            ]
        )
        for cat in JBB_CATEGORIES:
            if cat in combined:
                s = combined[cat]
                rate = s["blocked"] / s["total"] * 100 if s["total"] > 0 else 0
                emoji = "🟢" if rate >= 90 else "🟡" if rate >= 70 else "🔴"
                lines.append(f"| {emoji} {cat} | {s['total']} | {s['blocked']} | {rate:.1f}% |")
        lines.append("")

    # Missed sample
    all_missed = []
    for r in balanced_results:
        all_missed.extend(r.get("missed_sample", []))
    if all_missed:
        lines.extend(
            [
                "<details>",
                f"<summary>Missed attacks ({len(all_missed)} shown)</summary>",
                "",
                "| ID | Category | Goal | Intent | Risk |",
                "|----|----------|------|--------|------|",
            ]
        )
        for m in all_missed[:30]:
            goal = m["goal"].replace("|", "\\|")
            lines.append(f"| {m['id']} | {m['category']} | {goal} | {m['intent']} | {m['risk']:.2f} |")
        lines.extend(["", "</details>", ""])

    # Limitations
    lines.extend(
        [
            "## Limitations",
            "",
            "- Evaluates the **pre-LLM pipeline only** — keyword classifiers, ML scanners",
            "  (LLM Guard), and semantic embeddings (NeMo Guardrails). No LLM-as-judge.",
            "- Uses published jailbreak artifacts as an external attack set; does **not** measure",
            "  end-to-end provider responses or model-specific behavior.",
            "- Does not measure benign allow rate within the JailbreakBench dataset (all prompts",
            "  are attacks by design).",
            "- Attack transferability may vary across target models and providers.",
            "- PAIR-style attacks use sophisticated roleplay framing that is specifically designed",
            "  to bypass keyword-based and shallow ML detection — lower detection is expected.",
            "",
        ]
    )

    # Environment
    lines.extend(
        [
            "## Test Environment",
            "",
            "| | |",
            "|---|---|",
            f"| OS | {machine['os']} ({machine['arch']}) |",
            f"| CPU | {machine['cpu']} |",
            f"| RAM | {machine['ram_total_gb']} GB |",
            f"| Python | {machine['python']} |",
            f"| Date | {ts} |",
            "",
        ]
    )

    # About
    lines.extend(
        [
            "## About JailbreakBench",
            "",
            "JailbreakBench is a standardized benchmark for evaluating LLM jailbreak attacks",
            "and defenses, published at NeurIPS 2024 (Datasets & Benchmarks Track).",
            "",
            "- Paper: [arXiv:2404.01318](https://arxiv.org/abs/2404.01318)",
            "- Repository: [github.com/JailbreakBench](https://github.com/JailbreakBench/jailbreakbench)",
            "- Artifacts: [github.com/JailbreakBench/artifacts](https://github.com/JailbreakBench/artifacts)",
            "",
            "These prompts are published jailbreak artifacts from JailbreakBench, used here",
            "as an external attack set for pre-LLM detection evaluation. They represent real",
            "jailbreak prompts that successfully bypassed target models in the original research.",
            "",
            "## Reproduce",
            "",
            "```bash",
            "cd apps/proxy-service",
            "python -m benchmarks.bench_jailbreakbench",
            "# or: make benchmark-jailbreakbench",
            "```",
            "",
        ]
    )

    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description="AI Protector × JailbreakBench benchmark")
    parser.add_argument("--policy", type=str, default="balanced", choices=POLICIES.keys())
    parser.add_argument("--all-policies", action="store_true")
    parser.add_argument(
        "--methods",
        nargs="+",
        default=["PAIR", "GCG", "JBC", "prompt_with_random_search"],
        choices=ATTACK_SOURCES.keys(),
    )
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    policies = list(POLICIES.keys()) if args.all_policies else [args.policy]

    # Download dataset
    print("Downloading JailbreakBench artifacts...")
    all_prompts = download_artifacts(args.methods)
    total = sum(len(v) for v in all_prompts.values())
    print(f"Total: {total} unique jailbreak prompts\n")

    all_results: list[JBBResult] = []

    for policy in policies:
        for method, prompts in all_prompts.items():
            print(f"▸ {method} × {policy} ({len(prompts)} prompts)...")
            result = await run_jbb_benchmark(prompts, method, policy)
            all_results.append(result)

    print_results(all_results)

    # Save JSON
    result_dicts = [r.to_dict() for r in all_results]
    out_json = Path(args.output) if args.output else RESULTS_DIR / "jailbreakbench.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result_dicts, indent=2))
    print(f"JSON saved to {out_json}")

    # Generate markdown report
    machine = collect_machine_info()
    report = generate_jbb_report(result_dicts, machine)
    report_path = Path(__file__).resolve().parents[3] / "BENCHMARK_JAILBREAKBENCH.md"
    report_path.write_text(report)
    print(f"Report saved to {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
