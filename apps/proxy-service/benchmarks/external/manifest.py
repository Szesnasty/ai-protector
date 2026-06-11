"""Corpus integrity manifest.

The manifest records, per corpus file: a sha256, a count, and the set of
attack methods / strategies it contains. CI verifies the sha256 so a corpus
that was regenerated without going through review fails fast.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from benchmarks.external.schema import CORPUS_DIR, read_jsonl

MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
MANIFEST_VERSION = "1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _summarize_file(path: Path) -> dict:
    methods: set[str] = set()
    strategies: set[str] = set()
    surfaces: set[str] = set()
    count = 0
    source = path.stem
    source_version = "?"
    for rec in read_jsonl(path):
        count += 1
        methods.add(rec.attack_method)
        surfaces.add(rec.surface)
        if rec.strategy:
            strategies.add(rec.strategy)
        source = rec.source
        source_version = rec.source_version
    return {
        "source": source,
        "source_version": source_version,
        "file": f"corpus/{path.name}",
        "sha256": sha256_file(path),
        "count": count,
        "surfaces": sorted(surfaces),
        "attack_methods": sorted(methods),
        "strategies": sorted(strategies),
    }


def build_manifest(corpus_dir: Path = CORPUS_DIR, meta: dict | None = None) -> dict:
    """Scan ``corpus/*.jsonl`` and build the manifest dict."""
    sources = [_summarize_file(p) for p in sorted(corpus_dir.glob("*.jsonl"))]
    return {
        "version": MANIFEST_VERSION,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        "total_count": sum(s["count"] for s in sources),
        "meta": meta or {},
        "sources": sources,
    }


def write_manifest(corpus_dir: Path = CORPUS_DIR, meta: dict | None = None) -> dict:
    """Rebuild and persist the manifest. Returns the manifest dict."""
    manifest = build_manifest(corpus_dir, meta)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def verify_manifest(corpus_dir: Path = CORPUS_DIR) -> tuple[bool, list[str]]:
    """Verify every committed corpus file matches its recorded sha256.

    Returns ``(ok, problems)``. Fails on: missing manifest, missing file,
    sha256 mismatch, or a corpus file absent from the manifest.
    """
    problems: list[str] = []
    if not MANIFEST_PATH.exists():
        return False, [f"manifest not found at {MANIFEST_PATH}"]

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    recorded = {s["file"]: s for s in manifest.get("sources", [])}

    on_disk = {f"corpus/{p.name}" for p in corpus_dir.glob("*.jsonl")}
    for rel in sorted(on_disk - set(recorded)):
        problems.append(f"{rel}: present on disk but missing from manifest (regenerate manifest via --write)")

    for rel, entry in recorded.items():
        path = corpus_dir.parent / rel
        if not path.exists():
            problems.append(f"{rel}: listed in manifest but missing on disk")
            continue
        actual = sha256_file(path)
        if actual != entry["sha256"]:
            problems.append(f"{rel}: sha256 mismatch (corpus changed without re-manifest/review)")

    return (len(problems) == 0), problems
