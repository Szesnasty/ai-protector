"""Shared shields.io endpoint-badge writer.

Benchmarks emit a small JSON that shields.io renders as a dynamic badge:
    https://img.shields.io/endpoint?url=<raw URL to this JSON>

CI publishes these JSONs to the `badges` branch, so README badges always
reflect the latest CI-measured numbers — no hand-edited percentages.
"""

from __future__ import annotations

import json
from pathlib import Path


def _color(pct: float) -> str:
    if pct >= 90:
        return "brightgreen"
    if pct >= 80:
        return "green"
    if pct >= 70:
        return "yellowgreen"
    if pct >= 50:
        return "yellow"
    if pct >= 30:
        return "orange"
    return "red"


def write_shield_badge(path: str | Path, label: str, pct: float) -> None:
    """Write a shields.io endpoint badge JSON for ``pct`` (0–100)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schemaVersion": 1,
        "label": label,
        "message": f"{pct:.1f}%",
        "color": _color(pct),
    }
    p.write_text(json.dumps(data), encoding="utf-8")
    print(f"✓ badge written: {p}  ({label}: {pct:.1f}%)")
