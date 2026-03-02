"""Pre-download and warm-up LLM Guard ML models.

Run this script once before starting the server to avoid cold-start
latency on the first request.

Usage:
    cd apps/proxy-service
    source .venv/bin/activate
    python scripts/warmup_scanners.py
"""

from __future__ import annotations

import time


def main() -> None:
    print("Warming up LLM Guard scanners...")
    start = time.perf_counter()

    from llm_guard.input_scanners import (
        InvisibleText,
        PromptInjection,
        Secrets,
        Toxicity,
    )

    scanners = [
        ("PromptInjection", PromptInjection(threshold=0.5)),
        ("Toxicity", Toxicity(threshold=0.7)),
        ("Secrets", Secrets()),
        ("InvisibleText", InvisibleText()),
    ]

    test_prompt = "This is a warm-up test prompt for model initialization."

    for name, scanner in scanners:
        t0 = time.perf_counter()
        scanner.scan(test_prompt)
        elapsed = (time.perf_counter() - t0) * 1000
        print(f"  ✓ {name} ready ({elapsed:.0f}ms)")

    total = (time.perf_counter() - start) * 1000
    print(f"\nAll scanners warmed up in {total:.0f}ms")


if __name__ == "__main__":
    main()
