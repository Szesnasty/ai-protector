"""Reproducibility manifest — the record that makes a benchmark run provable.

A run is reproducible only if you can pin *exactly* what was tested and how it was
graded. The manifest captures the **recipe + a content hash**:

  - selection recipe: packs, categories, subcategories, sample_per_category, seed,
    and the resolve inputs (agent_type, safe_mode) that decide applicability;
  - pinned pack versions (drift detection if a pack is rebuilt);
  - the resolved scenario set (ordered ids) + a SHA-256 over (id, prompt, detector)
    so any change to the underlying attacks is detectable;
  - the grader fingerprint (deterministic detectors used).

`verify_manifest` re-resolves the recipe from the current packs and recomputes the
hash: equal ⇒ the exact same attack set + grading would run again; different ⇒ the
corpus drifted and the old numbers are no longer reproducible. That round-trip is what
"control you can prove" means for the benchmark itself.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from src.red_team.packs import TargetConfig
from src.red_team.packs.loader import (
    _DEFAULT_SAMPLE_SEED,
    FilteredPack,
    load_pack,
    resolve_filtered_pack,
)

MANIFEST_VERSION = "1.0"


def _detector_type(scenario) -> str:
    dt = scenario.detector.type
    return dt.value if hasattr(dt, "value") else str(dt)


def scenario_set_hash(scenarios) -> str:
    """SHA-256 over the ordered (id, prompt, detector-config) of the scenario set.

    Sorted by id so the hash is independent of iteration order; includes the detector
    config so a changed grading rule (not just a changed prompt) also changes the hash.
    """
    h = hashlib.sha256()
    for s in sorted(scenarios, key=lambda x: x.id):
        detector = s.detector.model_dump(mode="json") if hasattr(s.detector, "model_dump") else {}
        h.update(
            json.dumps(
                {"id": s.id, "prompt": s.prompt, "detector": detector},
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        )
    return "sha256:" + h.hexdigest()


def build_manifest(pack: str, target_config: dict[str, Any] | None, filtered: FilteredPack) -> dict[str, Any]:
    """Build the reproducibility manifest for a resolved run."""
    cfg = target_config or {}
    selection = cfg.get("selection") or {}
    is_selection = bool(selection.get("packs"))
    pack_names = selection.get("packs") or [pack]

    packs_meta: list[dict[str, str]] = []
    for name in pack_names:
        try:
            packs_meta.append({"name": name, "version": load_pack(name).version})
        except Exception:
            packs_meta.append({"name": name, "version": "unknown"})

    detectors = sorted({_detector_type(s) for s in filtered.scenarios})

    return {
        "manifest_version": MANIFEST_VERSION,
        "mode": "selection" if is_selection else "single",
        "selection": {
            "packs": pack_names,
            "categories": selection.get("categories") or [],
            "subcategories": selection.get("subcategories") or [],
            "filters": selection.get("filters") or [],
            "sample_per_category": selection.get("sample_per_category"),
            "seed": selection.get("seed", _DEFAULT_SAMPLE_SEED),
        },
        "resolve": {
            "agent_type": cfg.get("agent_type", "chatbot_api"),
            "safe_mode": bool(cfg.get("safe_mode", False)),
        },
        "packs": packs_meta,
        "scenario_count": len(filtered.scenarios),
        "scenario_ids": [s.id for s in filtered.scenarios],
        "scenario_set_hash": scenario_set_hash(filtered.scenarios),
        "grader": {"type": "deterministic", "detectors": detectors},
    }


def verify_manifest(manifest: dict[str, Any], packs_dir=None) -> dict[str, Any]:
    """Re-resolve the manifest's recipe against the current packs and compare hashes.

    Returns ``{"reproducible": bool, "expected_hash", "actual_hash",
    "expected_count", "actual_count"}``. ``reproducible`` is True iff the same attack
    set + grading would run again — the core auditable guarantee.
    """
    selection = manifest.get("selection") or {}
    resolve = manifest.get("resolve") or {}
    pack = (selection.get("packs") or ["selection"])[0]
    cfg = TargetConfig(
        agent_type=resolve.get("agent_type", "chatbot_api"),
        safe_mode=bool(resolve.get("safe_mode", False)),
    )
    # Mirror the ORIGINAL resolution path so ids (and thus the hash) match exactly:
    # single-pack runs use bare ids; selection runs use namespaced "<pack>::<id>".
    if manifest.get("mode") == "single":
        target_config: dict[str, Any] = {}
    else:
        target_config = {
            "selection": {
                "packs": selection.get("packs") or [],
                "categories": selection.get("categories") or [],
                "subcategories": selection.get("subcategories") or [],
                "filters": selection.get("filters") or [],
                "sample_per_category": selection.get("sample_per_category"),
                "seed": selection.get("seed", _DEFAULT_SAMPLE_SEED),
            },
        }
    filtered = resolve_filtered_pack(pack, target_config, cfg, available_detectors=None)
    actual_hash = scenario_set_hash(filtered.scenarios)
    expected_hash = manifest.get("scenario_set_hash")
    return {
        "reproducible": actual_hash == expected_hash,
        "expected_hash": expected_hash,
        "actual_hash": actual_hash,
        "expected_count": manifest.get("scenario_count"),
        "actual_count": len(filtered.scenarios),
    }
