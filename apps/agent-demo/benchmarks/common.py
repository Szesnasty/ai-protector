"""Shared helpers for the agent boundary benchmark.

Everything here is deterministic and dependency-light: the gates are pure
functions, so we build a minimal AgentState dict and replay frozen JSONL cases.
"""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
from typing import Any

BENCH_DIR = Path(__file__).resolve().parent
CORPORA_DIR = BENCH_DIR / "corpora"
RESULTS_DIR = BENCH_DIR / "results"
MANIFEST_PATH = BENCH_DIR / "manifest.json"
BASELINE_PATH = BENCH_DIR / "baseline.json"

# ── Decision vocabularies ─────────────────────────────────────────────
# The gates speak their own enums; the benchmark normalizes to a small,
# security-meaningful vocabulary so corpora are gate-agnostic.

# pre-tool gate → normalized
PRE_DECISION_MAP = {
    "ALLOW": "allow",
    "MODIFY": "allow",  # sanitized args, still executes → benign-allow for safety accounting
    "BLOCK": "block",
    "REQUIRE_CONFIRMATION": "require_confirmation",
}

# post-tool gate → normalized
POST_DECISION_MAP = {
    "PASS": "allow",
    "REDACT": "allow_redacted",
    "TRUNCATE": "allow",
    "BLOCK": "block",
}

# Which normalized decisions count as "the action/output was contained"
PRE_CONTAINED = {"block", "require_confirmation"}
POST_CONTAINED = {"block", "allow_redacted"}


# ── Corpus IO ─────────────────────────────────────────────────────────


def load_jsonl(name: str) -> list[dict[str, Any]]:
    """Load a frozen corpus file from corpora/."""
    path = CORPORA_DIR / name
    records: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def make_pre_state(record: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal AgentState for the pre-tool gate from a corpus record.

    session_id is intentionally empty so the limits check uses the in-memory
    legacy path (no Redis). `prior_blocked` seeds the escalation counter and
    `prior_tool_calls` seeds the legacy session call counter.
    """
    prior_blocked = int(record.get("prior_blocked", 0))
    prior_tool_calls = int(record.get("prior_tool_calls", 0))
    tool_calls: list[dict[str, Any]] = []
    # Blocked records (allowed=False) drive the escalation counter.
    for _ in range(prior_blocked):
        tool_calls.append({"tool": "x", "args": {}, "result": "blocked", "allowed": False})
    # Allowed records drive the legacy session-count limit.
    for _ in range(prior_tool_calls):
        tool_calls.append({"tool": "x", "args": {}, "result": "ok", "allowed": True})
    return {
        "allowed_tools": [],
        "user_role": record.get("role", ""),
        "message": record.get("message", ""),
        "chat_history": [],
        "tool_calls": tool_calls,
        "iterations": 0,
        "session_id": "",
    }


# ── Integrity (harvest-and-freeze) ────────────────────────────────────


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest() -> dict[str, str]:
    """sha256 of every committed corpus file, sorted for stability."""
    return {p.name: sha256_file(p) for p in sorted(CORPORA_DIR.glob("*.jsonl"))}


def verify_manifest() -> tuple[bool, list[str]]:
    """Return (ok, problems). Fails if a corpus changed without re-manifest."""
    if not MANIFEST_PATH.exists():
        return False, ["manifest.json missing — run `make benchmark-agent-manifest`"]
    expected = json.loads(MANIFEST_PATH.read_text())
    current = build_manifest()
    problems: list[str] = []
    for name, digest in expected.items():
        if name not in current:
            problems.append(f"corpus removed: {name}")
        elif current[name] != digest:
            problems.append(f"corpus changed without manifest update: {name}")
    for name in current:
        if name not in expected:
            problems.append(f"corpus added without manifest update: {name}")
    return (len(problems) == 0), problems


# ── Misc ──────────────────────────────────────────────────────────────


def collect_machine_info() -> dict[str, str]:
    return {
        "machine": platform.machine(),
        "system": platform.system(),
        "python": platform.python_version(),
    }


def pct(num: int, den: int) -> float:
    return round(100.0 * num / den, 1) if den else 0.0
