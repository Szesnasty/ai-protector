"""Fetch RAW source data for the Red Team Hub packs into _sources/ (git-ignored,
reproducible). Preserves each source's NATIVE subcategory, namespaced as
"family:subtype" (e.g. "harmful:cybercrime_intrusion") so taxonomy.to_unified()
resolves the unified bucket while the subtype stays for drill-down.

Pack YAMLs (detectors etc.) are built FROM these by build_packs.py. Graceful skip.
Run from apps/proxy-service:  python -m src.red_team.packs.fetch_sources
"""

from __future__ import annotations

import csv
import io
import json
import re
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "_sources"
OUT.mkdir(exist_ok=True)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")[:40]


# name, url, text_col, subcat_col|None, family, detector, license
GH_CSV = [
    (
        "harmbench",
        "https://raw.githubusercontent.com/centerforaisafety/HarmBench/main/data/behavior_datasets/harmbench_behaviors_text_all.csv",
        "Behavior",
        "SemanticCategory",
        "harmful",
        "refusal_pattern",
        "MIT",
    ),
    (
        "advbench",
        "https://raw.githubusercontent.com/llm-attacks/llm-attacks/main/data/advbench/harmful_behaviors.csv",
        "goal",
        None,
        "harmful",
        "refusal_pattern",
        "MIT",
    ),
]
# name, repo, config, split, text_field, subcat_field|None, family, detector, license, cap, jb_only
HF = [
    (
        "do_not_answer",
        "LibrAI/do-not-answer",
        None,
        "train",
        "question",
        "risk_area",
        "harmful",
        "refusal_pattern",
        "Apache-2.0",
        1000,
        False,
    ),
    (
        "in_the_wild_jailbreak",
        "TrustAIRLab/in-the-wild-jailbreak-prompts",
        "jailbreak_2023_12_25",
        "train",
        "prompt",
        None,
        "jailbreak",
        "refusal_pattern",
        "check",
        1500,
        True,
    ),
]


def _category(family: str, subraw: str | None) -> str:
    s = slug(subraw) if subraw else ""
    return f"{family}:{s}" if s else family


def _write(name: str, rows: list[dict], meta: dict) -> None:
    with open(OUT / f"{name}.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (OUT / f"{name}.meta.json").write_text(json.dumps(meta | {"count": len(rows)}, indent=2))
    subs = {r["category"] for r in rows}
    print(f"  [ok]  {name}: {len(rows)} rows, {len(subs)} subcats  ({meta['license']})")


def fetch_gh() -> None:
    for name, url, col, subcol, family, det, lic in GH_CSV:
        try:
            data = urllib.request.urlopen(url, timeout=30).read().decode("utf-8")
            rows, seen = [], set()
            for row in csv.DictReader(io.StringIO(data)):
                t = (row.get(col) or "").strip()
                if not t or len(t) <= 6 or t in seen:
                    continue
                seen.add(t)
                rows.append(
                    {
                        "prompt": t,
                        "source": name,
                        "category": _category(family, row.get(subcol) if subcol else None),
                        "detector": det,
                    }
                )
            _write(name, rows, {"source": name, "url": url, "family": family, "detector": det, "license": lic})
        except Exception as exc:  # noqa: BLE001
            print(f"  [skip] {name}: {type(exc).__name__}: {str(exc)[:110]}")


def fetch_hf() -> None:
    try:
        from datasets import load_dataset
    except ImportError:
        print("  [hf] `datasets` not installed — skipping HF sources")
        return
    for name, repo, cfg, split, field, subfield, family, det, lic, cap, jb_only in HF:
        try:
            ds = load_dataset(repo, cfg, split=split, streaming=True)
            rows, seen, kept = [], set(), 0
            for r in ds:
                if kept >= cap:
                    break
                if jb_only and str(r.get("jailbreak")).lower() != "true":
                    continue
                t = (r.get(field) or "").strip()
                if not t or len(t) <= 6 or t in seen:
                    continue
                seen.add(t)
                rows.append(
                    {
                        "prompt": t,
                        "source": name,
                        "category": _category(family, r.get(subfield) if subfield else None),
                        "detector": det,
                    }
                )
                kept += 1
            _write(name, rows, {"source": name, "repo": repo, "family": family, "detector": det, "license": lic})
        except Exception as exc:  # noqa: BLE001
            print(f"  [skip] {name}: {type(exc).__name__}: {str(exc)[:110]}")


if __name__ == "__main__":
    print("Fetching Red Team Hub source data → _sources/ …")
    fetch_gh()
    fetch_hf()
    print("\nDeferred (need dedicated adapters): BIPIA (indirect), garak (static probes), promptfoo (mixed detectors).")
