"""Pack Loader implementation.

Loads YAML/JSON scenario packs, validates against schema,
filters by target config & detector availability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.red_team.schemas import Pack, Scenario
from src.red_team.schemas.enums import AgentType, DetectorType

# Default packs directory (relative to proxy-service root)
_DEFAULT_PACKS_DIR = Path(__file__).resolve().parent / "data"


class PackLoadError(Exception):
    """Raised when a pack file cannot be loaded or validated."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TargetConfig:
    """Target configuration relevant to pack filtering."""

    agent_type: str = "chatbot_api"  # "chatbot_api" | "tool_calling"
    safe_mode: bool = False


@dataclass(frozen=True, slots=True)
class SkippedScenario:
    """A scenario that was filtered out, with reason."""

    scenario_id: str
    title: str
    reason: str  # "not_applicable" | "safe_mode" | "detector_unavailable"


@dataclass(frozen=True, slots=True)
class FilteredPack:
    """Result of loading + filtering a pack."""

    pack_name: str
    pack_version: str
    total_in_pack: int
    total_applicable: int
    skipped_count: int
    skipped_reasons: dict[str, int]
    scenarios: list[Scenario]
    skipped: list[SkippedScenario]
    system_prompt: str | None = None  # Pack-level system prompt (supports ${CANARY})

    def __post_init__(self) -> None:
        # Enforce counting invariants
        assert self.total_in_pack == self.total_applicable + self.skipped_count, (
            f"total_in_pack ({self.total_in_pack}) != "
            f"total_applicable ({self.total_applicable}) + skipped_count ({self.skipped_count})"
        )
        assert self.total_applicable == len(self.scenarios), (
            f"total_applicable ({self.total_applicable}) != len(scenarios) ({len(self.scenarios)})"
        )
        assert self.skipped_count == len(self.skipped), (
            f"skipped_count ({self.skipped_count}) != len(skipped) ({len(self.skipped)})"
        )
        assert self.skipped_count == sum(self.skipped_reasons.values()), (
            f"skipped_count ({self.skipped_count}) != sum(skipped_reasons) ({sum(self.skipped_reasons.values())})"
        )


@dataclass(frozen=True, slots=True)
class PackInfo:
    """Metadata about an available pack (for listing)."""

    name: str
    display_name: str
    description: str
    version: str
    scenario_count: int
    applicable_to: list[str]
    default_for: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pack loading
# ---------------------------------------------------------------------------

# In-memory cache for loaded packs (they're static per deployment)
_pack_cache: dict[str, Pack] = {}


def _resolve_packs_dir(packs_dir: Path | None) -> Path:
    return packs_dir if packs_dir is not None else _DEFAULT_PACKS_DIR


def load_pack(pack_name: str, packs_dir: Path | None = None) -> Pack:
    """Load and validate a pack from YAML/JSON file.

    Raises PackLoadError on file-not-found or validation failure.
    """
    if pack_name in _pack_cache:
        return _pack_cache[pack_name]

    pdir = _resolve_packs_dir(packs_dir)
    pack_file = _find_pack_file(pack_name, pdir)
    if pack_file is None:
        raise PackLoadError(f"Pack '{pack_name}' not found in {pdir}")

    try:
        raw = _read_pack_file(pack_file)
        pack = Pack(**raw)
    except Exception as exc:
        raise PackLoadError(f"Failed to load pack '{pack_name}' from {pack_file}: {exc}") from exc

    _pack_cache[pack_name] = pack
    return pack


# Only allow safe pack names: alphanumeric, underscore, hyphen, dot
_SAFE_PACK_NAME = re.compile(r"\A[A-Za-z0-9_.-]+\Z")

_PACK_EXTENSIONS = frozenset({".yaml", ".yml", ".json"})


def _find_pack_file(pack_name: str, packs_dir: Path) -> Path | None:
    """Find a pack file by name via directory listing.

    Enumerates files in *packs_dir* and matches by stem instead of
    constructing a path from user input — this prevents any path-traversal
    regardless of *pack_name* content.
    """
    if not pack_name or not _SAFE_PACK_NAME.match(pack_name):
        return None

    base_dir = packs_dir.resolve()
    if not base_dir.is_dir():
        return None

    # Iterate actual files — pack_name is only used in string comparison,
    # never in path construction, so no taint reaches the filesystem.
    for child in sorted(base_dir.iterdir()):
        if child.is_file() and child.suffix in _PACK_EXTENSIONS and child.stem == pack_name:
            return child
    return None


def _read_pack_file(path: Path) -> dict[str, Any]:
    """Read and parse a YAML or JSON pack file."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        import json

        return json.loads(text)
    return yaml.safe_load(text)


# ---------------------------------------------------------------------------
# Pack filtering
# ---------------------------------------------------------------------------


def filter_pack(
    pack: Pack,
    config: TargetConfig,
    available_detectors: set[str] | None = None,
) -> FilteredPack:
    """Filter scenarios based on target config and detector availability.

    Filtering rules applied in order:
    1. Target type: skip if scenario.applicable_to doesn't include config.agent_type
    2. Safe mode: skip if safe_mode=True and scenario.mutating=True
    3. Detector availability: skip if detector.type not in available_detectors
    """
    if available_detectors is None:
        # By default, all MVP detectors except llm_judge
        available_detectors = {dt.value for dt in DetectorType if dt != DetectorType.LLM_JUDGE}

    applicable: list[Scenario] = []
    skipped: list[SkippedScenario] = []
    reasons_count: dict[str, int] = {}

    for scenario in pack.scenarios:
        reason = _check_skip_reason(scenario, config, available_detectors)
        if reason is None:
            applicable.append(scenario)
        else:
            skipped.append(
                SkippedScenario(
                    scenario_id=scenario.id,
                    title=scenario.title,
                    reason=reason,
                )
            )
            reasons_count[reason] = reasons_count.get(reason, 0) + 1

    return FilteredPack(
        pack_name=pack.name,
        pack_version=pack.version,
        total_in_pack=len(pack.scenarios),
        total_applicable=len(applicable),
        skipped_count=len(skipped),
        skipped_reasons=reasons_count,
        scenarios=applicable,
        skipped=skipped,
        system_prompt=pack.system_prompt,
    )


def _check_skip_reason(
    scenario: Scenario,
    config: TargetConfig,
    available_detectors: set[str],
) -> str | None:
    """Return skip reason or None if scenario should run."""
    # 1. Target type filter
    try:
        agent_type_enum = AgentType(config.agent_type)
    except ValueError:
        agent_type_enum = None

    if agent_type_enum is not None and agent_type_enum not in scenario.applicable_to:
        return "not_applicable"

    # 2. Safe mode filter
    if config.safe_mode and scenario.mutating:
        return "safe_mode"

    # 3. Detector availability filter
    detector_type = scenario.detector.type
    if isinstance(detector_type, DetectorType):
        detector_type = detector_type.value
    if detector_type not in available_detectors:
        return "detector_unavailable"

    return None


# ---------------------------------------------------------------------------
# Pack listing
# ---------------------------------------------------------------------------


# Display name mapping
_DISPLAY_NAMES: dict[str, str] = {
    "core_security": "Core Security",
    "core_verified": "Core Verified",
    "unsafe_output": "Unsafe Output",
    "extended_advisory": "Extended Advisory",
    "agent_threats": "Agent Threats",
    "full_suite": "Full Suite",
    "jailbreakbench": "JailbreakBench",
}


def list_packs(packs_dir: Path | None = None) -> list[PackInfo]:
    """List all available packs with metadata."""
    pdir = _resolve_packs_dir(packs_dir)
    if not pdir.exists():
        return []

    result: list[PackInfo] = []
    for path in sorted(pdir.iterdir()):
        if path.suffix not in (".yaml", ".yml", ".json"):
            continue
        try:
            raw = _read_pack_file(path)
            pack_name = raw.get("name", path.stem)
            result.append(
                PackInfo(
                    name=pack_name,
                    display_name=_DISPLAY_NAMES.get(pack_name, pack_name.replace("_", " ").title()),
                    description=raw.get("description", ""),
                    version=raw.get("version", "0.0.0"),
                    scenario_count=raw.get("scenario_count", len(raw.get("scenarios", []))),
                    applicable_to=[str(a) for a in raw.get("applicable_to", [])],
                    default_for=raw.get("default_for", []),
                )
            )
        except Exception:
            continue  # Skip malformed packs in listing

    return result


def clear_cache() -> None:
    """Clear the in-memory pack cache (for testing)."""
    _pack_cache.clear()
