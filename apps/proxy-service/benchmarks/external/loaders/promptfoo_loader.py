"""Normalize a promptfoo red-team export into the canonical corpus.

Harvest-and-freeze: this runs OFFLINE (never in CI). It reads the YAML/JSON
produced by ``promptfoo redteam generate`` and writes ``corpus/promptfoo.jsonl``,
then rebuilds the manifest. The resulting corpus is committed via a reviewed PR.

    python -m benchmarks.external.loaders.promptfoo_loader \
        --input benchmarks/external/harvest/raw/redteam.yaml

promptfoo's generated tests look roughly like::

    tests:
      - vars: { prompt: "<attack text>" }
        metadata: { pluginId: "harmful:hate", strategyId: "rot13" }

Plugin/strategy ids vary across promptfoo versions — the OWASP map below is
best-effort with a safe default; extend it as needed.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmarks.external.manifest import write_manifest
from benchmarks.external.schema import CORPUS_DIR, CorpusRecord, canonical_id, validate, write_jsonl

SOURCE = "promptfoo"

# promptfoo plugin id (or its prefix) → OWASP LLM Top 10. Longest-prefix wins.
_OWASP_BY_PLUGIN: dict[str, str] = {
    "prompt-injection": "LLM01",
    "indirect-prompt-injection": "LLM01",
    "jailbreak": "LLM01",
    "hijacking": "LLM01",
    "ascii-smuggling": "LLM01",
    "harmful": "LLM01",
    "prompt-extraction": "LLM07",
    "system-prompt": "LLM07",
    "pii": "LLM02",
    "harmful:privacy": "LLM02",
    "overreliance": "LLM09",
    "imitation": "LLM09",
}


def _owasp_for(plugin: str) -> str:
    best = ""
    for key in _OWASP_BY_PLUGIN:
        if (plugin == key or plugin.startswith(key)) and len(key) > len(best):
            best = key
    return _OWASP_BY_PLUGIN.get(best, "LLM01")


def _load_export(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        import yaml  # promptfoo default output

        return yaml.safe_load(text)
    return json.loads(text)


def _iter_tests(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Find the list of generated test cases in a promptfoo export."""
    if isinstance(data.get("tests"), list):
        return data["tests"]
    # Some exports nest under defaultTest/redteam — fall back to a deep scan.
    for value in data.values():
        if isinstance(value, dict) and isinstance(value.get("tests"), list):
            return value["tests"]
    return []


def _extract_prompt(test: dict[str, Any], inject_var: str | None) -> str | None:
    vars_ = test.get("vars") or {}
    if not isinstance(vars_, dict):
        return None
    if inject_var and inject_var in vars_:
        return str(vars_[inject_var])
    if "prompt" in vars_:
        return str(vars_["prompt"])
    # Single-var case: take the only value.
    if len(vars_) == 1:
        return str(next(iter(vars_.values())))
    return None


def normalize(data: dict[str, Any], inject_var: str | None, source_version: str) -> list[CorpusRecord]:
    harvested_at = datetime.now(UTC).strftime("%Y-%m-%d")
    records: list[CorpusRecord] = []
    seen: set[str] = set()

    for test in _iter_tests(data):
        prompt = _extract_prompt(test, inject_var)
        if not prompt:
            continue
        meta = test.get("metadata") or {}
        plugin = str(meta.get("pluginId") or meta.get("plugin") or "unknown")
        strategy = meta.get("strategyId") or meta.get("strategy") or None
        strategy = str(strategy) if strategy else None

        rec = CorpusRecord(
            id=canonical_id(SOURCE, plugin, strategy, prompt),
            source=SOURCE,
            source_version=source_version,
            harvested_at=harvested_at,
            surface="proxy",  # iteration 1: proxy surface only
            owasp=_owasp_for(plugin),
            attack_method=plugin,
            prompt=prompt,
            expected="BLOCK",  # red-team tests are attacks
            strategy=strategy,
            tags=["promptfoo"] + ([strategy] if strategy else []),
        )
        if rec.id in seen:
            continue
        seen.add(rec.id)
        records.append(rec)

    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize promptfoo redteam export → canonical corpus")
    parser.add_argument("--input", required=True, help="promptfoo redteam generate output (.yaml/.json)")
    parser.add_argument("--output", default=str(CORPUS_DIR / "promptfoo.jsonl"))
    parser.add_argument("--inject-var", default=None, help="vars key holding the attack text (default: prompt)")
    parser.add_argument("--source-version", default="unknown", help="installed promptfoo version (pin it)")
    args = parser.parse_args()

    data = _load_export(Path(args.input))
    records = normalize(data, args.inject_var, args.source_version)

    problems: list[str] = []
    for rec in records:
        problems.extend(validate(rec))
    if problems:
        print("✗ validation problems:")
        for p in problems[:20]:
            print(f"  - {p}")
        return 1

    n = write_jsonl(Path(args.output), records)
    print(f"✓ wrote {n} promptfoo records to {args.output}")
    manifest = write_manifest()
    print(f"✓ manifest rebuilt: {manifest['total_count']} records across {len(manifest['sources'])} file(s)")
    print("→ review the diff and commit corpus/ + manifest.json via PR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
