"""Pack Loader — loads, validates, and filters scenario packs.

Public API:
    load_pack(pack_name, packs_dir?) → Pack
    filter_pack(pack, config, available_detectors) → FilteredPack
    list_packs(packs_dir?) → list[PackInfo]
    Dataclasses: FilteredPack, SkippedScenario, PackInfo, TargetConfig, PackLoadError
"""

from src.red_team.packs.loader import (
    FilteredPack,
    PackInfo,
    PackLoadError,
    SkippedScenario,
    TargetConfig,
    filter_pack,
    list_packs,
    load_pack,
)

__all__ = [
    "FilteredPack",
    "PackInfo",
    "PackLoadError",
    "SkippedScenario",
    "TargetConfig",
    "filter_pack",
    "list_packs",
    "load_pack",
]
