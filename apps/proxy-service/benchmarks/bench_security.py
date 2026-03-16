"""Security detection benchmark — measures attack detection rate.

Tests the pre-LLM pipeline against:
1. Internal AI Protector scenarios (358 attacks, 23 categories)
2. JailbreakBench dataset (100 harmful behaviors, NeurIPS 2024)

Usage:
    cd apps/proxy-service
    python -m benchmarks.bench_security
    python -m benchmarks.bench_security --policy strict
    python -m benchmarks.bench_security --all-policies
    python -m benchmarks.bench_security --include-jailbreakbench
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path

from benchmarks.common import DATA_DIR, POLICIES, RESULTS_DIR, build_pre_llm_pipeline, make_state

JBB_CACHE_PATH = Path(__file__).parent / "datasets" / "jailbreakbench.json"


# ── Data loaders ──────────────────────────────────────────────────────


def load_internal_scenarios() -> list[dict]:
    """Load all internal attack scenarios (playground + agent)."""
    scenarios: list[dict] = []

    for file_name in ("playground.json", "agent.json"):
        path = DATA_DIR / file_name
        if not path.exists():
            continue
        source = file_name.replace(".json", "")
        with open(path) as f:
            data = json.load(f)
        for group in data:
            category = group["label"]
            for item in group.get("items", []):
                scenarios.append(
                    {
                        "id": item.get("id", "?"),
                        "source": f"ai-protector/{source}",
                        "category": category,
                        "prompt": item["prompt"],
                        "expected": item.get("expectedDecision", "ALLOW"),
                    }
                )

    return scenarios


def load_jailbreakbench() -> list[dict]:
    """Load JailbreakBench behaviors.

    Uses cached dataset if available, otherwise downloads via the
    jailbreakbench library (pip install jailbreakbench).
    """
    if JBB_CACHE_PATH.exists():
        with open(JBB_CACHE_PATH) as f:
            return json.load(f)

    try:
        import jailbreakbench as jbb
    except ImportError:
        print(
            "  ⚠ jailbreakbench not installed. Run: pip install jailbreakbench\n"
            "    Or provide cached dataset at benchmarks/datasets/jailbreakbench.json"
        )
        return []

    scenarios: list[dict] = []

    # Load artifact prompts from well-known attack methods
    for method in ("PAIR", "GCG", "JBC", "prompt_with_random_search"):
        for model in ("vicuna-13b-v1.5", "llama-2-7b-chat-hf"):
            try:
                artifact = jbb.read_artifact(method=method, model_name=model)
            except Exception:
                continue
            for jb in artifact.jailbreaks:
                if not jb.prompt:
                    continue
                scenarios.append(
                    {
                        "id": f"JBB-{method}-{model}-{jb.index}",
                        "source": f"jailbreakbench/{method}",
                        "category": jb.category if hasattr(jb, "category") else method,
                        "prompt": jb.prompt,
                        "expected": "BLOCK",
                    }
                )

    if not scenarios:
        # Fallback: load base behaviors as simple prompts
        try:
            dataset = jbb.read_dataset()
            for i, behavior in enumerate(dataset.behaviors):
                goal = behavior.Goal if hasattr(behavior, "Goal") else str(behavior)
                scenarios.append(
                    {
                        "id": f"JBB-behavior-{i}",
                        "source": "jailbreakbench/behaviors",
                        "category": behavior.Category if hasattr(behavior, "Category") else "unknown",
                        "prompt": goal,
                        "expected": "BLOCK",
                    }
                )
        except Exception as exc:
            print(f"  ⚠ Failed to load JailbreakBench dataset: {exc}")
            return []

    # Cache for next run
    JBB_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(JBB_CACHE_PATH, "w") as f:
        json.dump(scenarios, f, indent=2)
    print(f"  Cached {len(scenarios)} JailbreakBench scenarios to {JBB_CACHE_PATH}")

    return scenarios


# ── Benchmark runner ──────────────────────────────────────────────────


@dataclass
class DetectionResult:
    policy: str
    source: str
    total: int = 0
    true_positive: int = 0  # attack correctly blocked
    true_negative: int = 0  # safe correctly allowed
    false_positive: int = 0  # safe incorrectly blocked
    false_negative: int = 0  # attack incorrectly allowed
    categories: dict[str, dict] = field(default_factory=dict)
    missed: list[dict] = field(default_factory=list)

    @property
    def detection_rate(self) -> float:
        attacks = self.true_positive + self.false_negative
        return self.true_positive / attacks if attacks > 0 else 0.0

    @property
    def false_positive_rate(self) -> float:
        safe = self.true_negative + self.false_positive
        return self.false_positive / safe if safe > 0 else 0.0

    def record(self, scenario: dict, decision: str, risk_score: float, intent: str) -> None:
        self.total += 1
        expected = scenario["expected"]
        cat = scenario["category"]

        if cat not in self.categories:
            self.categories[cat] = {"total": 0, "detected": 0, "missed": 0, "is_attack_category": True}
        self.categories[cat]["total"] += 1

        is_attack = expected in ("BLOCK", "MODIFY")
        is_blocked = decision in ("BLOCK", "MODIFY")

        if not is_attack:
            self.categories[cat]["is_attack_category"] = False

        if is_attack and is_blocked:
            self.true_positive += 1
            self.categories[cat]["detected"] += 1
        elif is_attack and not is_blocked:
            self.false_negative += 1
            self.categories[cat]["missed"] += 1
            self.missed.append(
                {
                    "id": scenario["id"],
                    "category": cat,
                    "prompt": scenario["prompt"][:120],
                    "got": decision,
                    "risk": risk_score,
                    "intent": intent,
                }
            )
        elif not is_attack and is_blocked:
            self.false_positive += 1
            self.categories[cat]["missed"] += 1
        else:
            self.true_negative += 1
            self.categories[cat]["detected"] += 1

    def to_dict(self) -> dict:
        return {
            "policy": self.policy,
            "source": self.source,
            "total": self.total,
            "true_positive": self.true_positive,
            "true_negative": self.true_negative,
            "false_positive": self.false_positive,
            "false_negative": self.false_negative,
            "detection_rate": round(self.detection_rate * 100, 1),
            "false_positive_rate": round(self.false_positive_rate * 100, 1),
            "categories": self.categories,
            "missed_sample": self.missed[:20],
        }


async def run_security_bench(
    scenarios: list[dict],
    policy_name: str,
    source_label: str,
) -> DetectionResult:
    """Run all scenarios through the pipeline and measure detection rate."""
    pipeline = build_pre_llm_pipeline()
    result = DetectionResult(policy=policy_name, source=source_label)

    # Warmup
    state = make_state("warmup prompt", policy_name)
    await pipeline.ainvoke(state)

    for i, scenario in enumerate(scenarios):
        state = make_state(scenario["prompt"], policy_name)
        try:
            out = await pipeline.ainvoke(state)
        except Exception as exc:
            result.record(scenario, "ERROR", 0.0, str(exc))
            continue

        decision = out.get("decision", "ERROR")
        risk_score = out.get("risk_score", 0.0)
        intent = out.get("intent", "?")
        result.record(scenario, decision, risk_score, intent)

        if (i + 1) % 50 == 0:
            print(f"    {i + 1}/{len(scenarios)} processed...")

    return result


def print_results(results: list[DetectionResult]) -> None:
    """Print detection results as a table."""
    header = (
        f"{'Policy':<10} {'Source':<28} {'Total':>6} {'Detect%':>8} {'FP%':>6} {'TP':>5} {'FN':>5} {'FP':>5} {'TN':>5}"
    )
    sep = "-" * len(header)

    print(f"\n{'=' * len(header)}")
    print("  AI Protector — Security Detection Benchmark")
    print(f"{'=' * len(header)}")
    print(header)
    print(sep)

    for r in results:
        print(
            f"{r.policy:<10} {r.source:<28} {r.total:>6} "
            f"{r.detection_rate * 100:>7.1f}% {r.false_positive_rate * 100:>5.1f}% "
            f"{r.true_positive:>5} {r.false_negative:>5} {r.false_positive:>5} {r.true_negative:>5}"
        )

    # Print missed attacks (false negatives)
    for r in results:
        if r.missed:
            print(f"\n  Missed attacks ({r.policy} / {r.source}):")
            for m in r.missed[:10]:
                print(f"    [{m['id']}] {m['category']}: intent={m['intent']}, risk={m['risk']:.2f}")
                print(f"      {m['prompt']}")

    # Per-category breakdown for the first result
    if results:
        r = results[0]
        print(f"\n  Per-category breakdown ({r.policy} / {r.source}):")
        print(f"  {'Category':<30} {'Total':>6} {'Detected':>9} {'Rate':>7}")
        print(f"  {'-' * 55}")
        for cat, stats in sorted(r.categories.items()):
            rate = stats["detected"] / stats["total"] * 100 if stats["total"] > 0 else 0
            marker = " ✗" if rate < 100 else ""
            print(f"  {cat:<30} {stats['total']:>6} {stats['detected']:>9} {rate:>6.1f}%{marker}")

    print()


async def main() -> None:
    parser = argparse.ArgumentParser(description="AI Protector security detection benchmark")
    parser.add_argument("--policy", type=str, default="balanced", choices=POLICIES.keys())
    parser.add_argument("--all-policies", action="store_true")
    parser.add_argument("--include-jailbreakbench", action="store_true", help="Include JailbreakBench dataset")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    policies = list(POLICIES.keys()) if args.all_policies else [args.policy]

    # Load scenarios
    internal = load_internal_scenarios()
    print(f"Loaded {len(internal)} internal scenarios")

    jbb_scenarios: list[dict] = []
    if args.include_jailbreakbench:
        jbb_scenarios = load_jailbreakbench()
        print(f"Loaded {len(jbb_scenarios)} JailbreakBench scenarios")

    all_results: list[dict] = []

    for policy in policies:
        print(f"\n▸ Testing policy: {policy}")

        # Internal scenarios
        print(f"  Running {len(internal)} internal scenarios...")
        r = await run_security_bench(internal, policy, "ai-protector/internal")
        all_results.append(r.to_dict())

        # JailbreakBench
        if jbb_scenarios:
            print(f"  Running {len(jbb_scenarios)} JailbreakBench scenarios...")
            r_jbb = await run_security_bench(jbb_scenarios, policy, "jailbreakbench")
            all_results.append(r_jbb.to_dict())

    # Print
    detection_results: list[DetectionResult] = []
    for d in all_results:
        dr = DetectionResult(policy=d["policy"], source=d["source"])
        dr.total = d["total"]
        dr.true_positive = d["true_positive"]
        dr.true_negative = d["true_negative"]
        dr.false_positive = d["false_positive"]
        dr.false_negative = d["false_negative"]
        dr.categories = d["categories"]
        dr.missed = d.get("missed_sample", [])
        detection_results.append(dr)
    print_results(detection_results)

    # Save JSON
    out_path = Path(args.output) if args.output else RESULTS_DIR / "security.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(all_results, indent=2))
    print(f"Results saved to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
