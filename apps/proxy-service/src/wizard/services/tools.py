"""Smart-default logic for agent tools (spec 27a)."""

from __future__ import annotations

from src.wizard.models import RATE_LIMIT_DEFAULTS, AccessType, AgentTool, Sensitivity


def apply_smart_defaults(tool: AgentTool) -> AgentTool:
    """Set requires_confirmation and rate_limit based on access_type + sensitivity.

    Rules:
        - access_type=write AND sensitivity >= high → requires_confirmation = true
        - rate_limit not explicitly set → use RATE_LIMIT_DEFAULTS[sensitivity]
    """
    # Auto-confirm for write + high/critical
    if tool.access_type == AccessType.WRITE and tool.sensitivity in (
        Sensitivity.HIGH,
        Sensitivity.CRITICAL,
    ):
        tool.requires_confirmation = True
    elif tool.access_type == AccessType.READ and tool.sensitivity in (
        Sensitivity.LOW,
        Sensitivity.MEDIUM,
    ):
        # Explicit read + low/medium → no confirmation (unless explicitly overridden)
        tool.requires_confirmation = False

    # Default rate-limit if not explicitly provided
    if tool.rate_limit is None:
        tool.rate_limit = RATE_LIMIT_DEFAULTS.get(tool.sensitivity)

    return tool
