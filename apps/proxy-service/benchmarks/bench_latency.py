"""Latency benchmark — measures per-node and total pipeline overhead.

Runs the pre-LLM pipeline (parse → intent → rules → scanners → decision)
with no LLM call, no network, no database.  Measures pure CPU overhead
that AI Protector adds to every request.

Usage:
    cd apps/proxy-service
    python -m benchmarks.bench_latency                 # default: 50 iterations, balanced
    python -m benchmarks.bench_latency --iterations 200
    python -m benchmarks.bench_latency --policy strict
    python -m benchmarks.bench_latency --all-policies
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

from benchmarks.common import POLICIES, RESULTS_DIR, SAMPLE_PROMPTS, build_pre_llm_pipeline, make_state

PIPELINE_NODES = ["parse", "intent", "rules", "scanners", "decision"]


@dataclass
class LatencyResult:
    policy: str
    prompt_type: str
    iterations: int
    total_ms: list[float] = field(default_factory=list)
    node_timings: dict[str, list[float]] = field(default_factory=dict)

    def add(self, state: dict, elapsed_ms: float) -> None:
        self.total_ms.append(elapsed_ms)
        for node, ms in state.get("node_timings", {}).items():
            self.node_timings.setdefault(node, []).append(ms)

    def stats(self, values: list[float]) -> dict:
        if not values:
            return {}
        s = sorted(values)
        n = len(s)
        return {
            "min": round(s[0], 2),
            "p50": round(s[n // 2], 2),
            "p95": round(s[int(n * 0.95)], 2),
            "p99": round(s[int(n * 0.99)], 2),
            "max": round(s[-1], 2),
            "mean": round(statistics.mean(s), 2),
            "stdev": round(statistics.stdev(s), 2) if n > 1 else 0.0,
        }

    def to_dict(self) -> dict:
        return {
            "policy": self.policy,
            "prompt_type": self.prompt_type,
            "iterations": self.iterations,
            "total": self.stats(self.total_ms),
            "nodes": {node: self.stats(times) for node, times in self.node_timings.items()},
        }


async def run_latency_bench(
    policy_name: str,
    iterations: int = 50,
    warmup: int = 3,
) -> list[dict]:
    """Run latency benchmark for a single policy across all prompt types."""
    pipeline = build_pre_llm_pipeline()
    results: list[dict] = []

    for prompt_type, prompt in SAMPLE_PROMPTS.items():
        # Warmup (load ML models, JIT, caches)
        for _ in range(warmup):
            state = make_state(prompt, policy_name)
            await pipeline.ainvoke(state)

        result = LatencyResult(
            policy=policy_name,
            prompt_type=prompt_type,
            iterations=iterations,
        )

        for _ in range(iterations):
            state = make_state(prompt, policy_name)
            t0 = time.perf_counter()
            out = await pipeline.ainvoke(state)
            elapsed = (time.perf_counter() - t0) * 1000
            result.add(out, elapsed)

        results.append(result.to_dict())

    return results


def print_table(all_results: list[dict]) -> None:
    """Print a human-readable latency table."""
    header = f"{'Policy':<10} {'Prompt Type':<22} {'p50':>8} {'p95':>8} {'p99':>8} {'mean':>8} {'stdev':>8}"
    sep = "-" * len(header)

    print(f"\n{'=' * len(header)}")
    print("  AI Protector — Latency Benchmark (pre-LLM pipeline, ms)")
    print(f"{'=' * len(header)}")
    print(header)
    print(sep)

    for r in all_results:
        t = r["total"]
        print(
            f"{r['policy']:<10} {r['prompt_type']:<22} "
            f"{t['p50']:>8.2f} {t['p95']:>8.2f} {t['p99']:>8.2f} "
            f"{t['mean']:>8.2f} {t['stdev']:>8.2f}"
        )

    # Node breakdown for first result
    if all_results:
        print(f"\n{'─' * len(header)}")
        print(f"  Node breakdown (first prompt type: {all_results[0]['prompt_type']})")
        print(f"{'─' * len(header)}")
        print(f"  {'Node':<12} {'p50':>8} {'p95':>8} {'mean':>8}")
        print(f"  {'-' * 40}")
        for node in PIPELINE_NODES:
            if node in all_results[0]["nodes"]:
                ns = all_results[0]["nodes"][node]
                print(f"  {node:<12} {ns['p50']:>8.2f} {ns['p95']:>8.2f} {ns['mean']:>8.2f}")

    print()


async def main() -> None:
    parser = argparse.ArgumentParser(description="AI Protector latency benchmark")
    parser.add_argument("--iterations", type=int, default=50, help="Iterations per prompt (default: 50)")
    parser.add_argument("--warmup", type=int, default=3, help="Warmup iterations (default: 3)")
    parser.add_argument("--policy", type=str, default="balanced", choices=POLICIES.keys())
    parser.add_argument("--all-policies", action="store_true", help="Benchmark all policies")
    parser.add_argument("--output", type=str, default=None, help="Output JSON path")
    args = parser.parse_args()

    policies = list(POLICIES.keys()) if args.all_policies else [args.policy]
    all_results: list[dict] = []

    for policy in policies:
        print(f"\n▸ Benchmarking policy: {policy} ({args.iterations} iterations)...")
        results = await run_latency_bench(policy, args.iterations, args.warmup)
        all_results.extend(results)

    print_table(all_results)

    # Save JSON
    out_path = Path(args.output) if args.output else RESULTS_DIR / "latency.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(all_results, indent=2))
    print(f"Results saved to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
