"""shields.io endpoint badge writer (same format as the proxy benchmark)."""

from __future__ import annotations

import json
from pathlib import Path


def _color(pct: float, *, higher_is_better: bool = True) -> str:
    v = pct if higher_is_better else 100 - pct
    if v >= 99:
        return "brightgreen"
    if v >= 90:
        return "green"
    if v >= 75:
        return "yellowgreen"
    if v >= 50:
        return "orange"
    return "red"


def write_shield_badge(path: str | Path, label: str, pct: float, *, higher_is_better: bool = True) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schemaVersion": 1,
        "label": label,
        "message": f"{pct:.1f}%",
        "color": _color(pct, higher_is_better=higher_is_better),
    }
    p.write_text(json.dumps(data), encoding="utf-8")
    print(f"✓ badge written: {p}  ({label}: {pct:.1f}%)")
