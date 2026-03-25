"""Poll benchmark run until complete, then print results."""

import sys
import time

import httpx

run_id = sys.argv[1] if len(sys.argv) > 1 else "7d48fe45-71ca-42ec-a7b5-14ad8a73bcc6"

for attempt in range(30):
    time.sleep(10)
    r = httpx.get(f"http://localhost:8000/v1/benchmark/runs/{run_id}", timeout=10)
    data = r.json()
    status = data["status"]
    score = data.get("score")
    print(f"[{attempt + 1}] Status: {status}, Score: {score}")

    if status in ("completed", "failed", "cancelled"):
        r2 = httpx.get(f"http://localhost:8000/v1/benchmark/runs/{run_id}/results", timeout=10)
        if r2.status_code == 200:
            results = r2.json()
            if isinstance(results, dict) and "results" in results:
                results = results["results"]
            if isinstance(results, list):
                passed = sum(1 for r in results if r.get("outcome") == "passed")
                failed = sum(1 for r in results if r.get("outcome") == "failed")
                skipped = sum(1 for r in results if r.get("outcome") == "skipped")
                print(f"\nTotal: {len(results)}  Passed: {passed}  Failed: {failed}  Skipped: {skipped}")
                print(f"\n{'ID':15s} {'OUTCOME':10s} {'LATENCY':>8s}")
                print("-" * 35)
                for res in results:
                    sid = res.get("scenario_id", "?")
                    outcome = res.get("outcome", "?")
                    lat = res.get("latency_ms", 0) or 0
                    marker = "<<<" if outcome == "failed" else ""
                    print(f"{sid:15s} {outcome:10s} {lat:7.0f}ms {marker}")
        break
