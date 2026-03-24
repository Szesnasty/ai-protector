"""Detector registry — maps DetectorType → detector function."""

from __future__ import annotations

from typing import Protocol

from src.red_team.schemas.dataclasses import EvalResult, RawTargetResponse


class DetectorFn(Protocol):
    """Protocol for detector functions."""

    def __call__(self, config: object, response: RawTargetResponse) -> EvalResult: ...


_registry: dict[str, DetectorFn] = {}


def register_detector(detector_type: str, fn: DetectorFn) -> None:
    """Register a detector function for a given type."""
    _registry[detector_type] = fn


def get_detector(detector_type: str) -> DetectorFn | None:
    """Look up a detector function by type. Returns None if not registered."""
    return _registry.get(detector_type)


def is_available(detector_type: str) -> bool:
    """Check if a detector is registered."""
    return detector_type in _registry


def list_available() -> set[str]:
    """Return all registered detector type names."""
    return set(_registry.keys())


def clear_registry() -> None:
    """Clear all registered detectors (for testing)."""
    _registry.clear()
