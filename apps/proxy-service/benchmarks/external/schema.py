"""Canonical attack-corpus schema + JSONL IO.

One JSONL line per attack, normalized across all sources (promptfoo, seed,
static datasets). Kept deliberately small and stable so the frozen corpus is
diff-able and the replay runner is source-agnostic.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"

# Decisions that count as "attack detected" when replaying through the pipeline.
DETECTED_DECISIONS = frozenset({"BLOCK", "MODIFY"})

# Allowed values for a few enum-like fields (validated softly, not enforced).
SURFACES = frozenset({"proxy", "agent"})
EXPECTED = frozenset({"BLOCK", "MODIFY", "ALLOW"})


@dataclass
class CorpusRecord:
    """A single normalized attack (or benign control) in the corpus."""

    id: str
    source: str  # "promptfoo" | "seed" | "<dataset>"
    source_version: str
    harvested_at: str  # ISO date, e.g. "2026-06-11"
    surface: str  # "proxy" | "agent"
    owasp: str  # OWASP LLM Top 10 id, e.g. "LLM01"
    attack_method: str  # plugin / family, e.g. "jailbreak", "harmful:hate"
    prompt: str
    expected: str  # "BLOCK" | "MODIFY" | "ALLOW"
    strategy: str | None = None  # obfuscation strategy, e.g. "rot13"; None for plain
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> CorpusRecord:
        known = {f for f in cls.__dataclass_fields__}  # noqa: C416
        return cls(**{k: v for k, v in data.items() if k in known})


def canonical_id(source: str, attack_method: str, strategy: str | None, prompt: str) -> str:
    """Stable id from (source, attack_method, strategy, prompt).

    Re-harvesting the same attack yields the same id, so corpus diffs are
    meaningful (additions/removals, not churn).
    """
    h = hashlib.sha256(f"{source}|{attack_method}|{strategy or ''}|{prompt}".encode()).hexdigest()[:12]
    prefix = source[:4]
    return f"{prefix}-{h}"


def validate(record: CorpusRecord) -> list[str]:
    """Return a list of soft validation problems (empty = ok)."""
    problems: list[str] = []
    if not record.prompt.strip():
        problems.append(f"{record.id}: empty prompt")
    if record.surface not in SURFACES:
        problems.append(f"{record.id}: unknown surface {record.surface!r}")
    if record.expected not in EXPECTED:
        problems.append(f"{record.id}: unknown expected {record.expected!r}")
    return problems


# ── JSONL IO ──────────────────────────────────────────────────────────


def write_jsonl(path: Path, records: Iterable[CorpusRecord]) -> int:
    """Write records as one JSON object per line (sorted keys for stable diffs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec.to_dict(), ensure_ascii=False, sort_keys=True))
            f.write("\n")
            count += 1
    return count


def read_jsonl(path: Path) -> Iterator[CorpusRecord]:
    """Yield CorpusRecord from a JSONL file."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield CorpusRecord.from_dict(json.loads(line))


def load_corpus(corpus_dir: Path = CORPUS_DIR, surface: str | None = None) -> list[CorpusRecord]:
    """Load every ``corpus/*.jsonl`` file, optionally filtered by surface."""
    records: list[CorpusRecord] = []
    for path in sorted(corpus_dir.glob("*.jsonl")):
        for rec in read_jsonl(path):
            if surface is None or rec.surface == surface:
                records.append(rec)
    return records
