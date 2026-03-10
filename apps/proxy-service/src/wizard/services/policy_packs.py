"""Policy pack templates (spec 28c).

Each pack defines scanner toggles, thresholds, limit tiers,
and redaction behaviour. Packs are immutable templates —
agents reference a pack by name and may override individual values.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScannerConfig:
    """Scanner toggle + threshold configuration."""

    injection_detection: bool = True
    injection_threshold: float = 0.5
    pii_redaction: bool = True
    pii_mode: str = "mask"  # mask | block | log | off
    secrets_scanning: bool = True
    toxicity_detection: bool = True
    toxicity_threshold: float = 0.6
    nemo_guardrails: bool = True


@dataclass(frozen=True)
class OutputFilteringConfig:
    """Output-side filtering configuration."""

    pii_redaction: bool = True
    secrets_scanning: bool = True
    injection_detection: bool = True
    max_output_size: int = 4000


@dataclass(frozen=True)
class ConfirmationConfig:
    """Confirmation requirements."""

    required_for_sensitivity: tuple[str, ...] = ("high", "critical")
    timeout_seconds: int = 300


@dataclass(frozen=True)
class LimitTier:
    """Budget limits for a single tier."""

    max_tool_calls_per_session: int = 20
    max_tokens_in: int = 8000
    max_tokens_out: int = 4000
    max_cost_usd: float = 0.50


# ── Default limit tiers (low / medium / high / very_high) ────────────

LOW_TIER = LimitTier(
    max_tool_calls_per_session=20,
    max_tokens_in=8000,
    max_tokens_out=4000,
    max_cost_usd=0.50,
)

MEDIUM_TIER = LimitTier(
    max_tool_calls_per_session=50,
    max_tokens_in=16000,
    max_tokens_out=8000,
    max_cost_usd=2.00,
)

HIGH_TIER = LimitTier(
    max_tool_calls_per_session=100,
    max_tokens_in=32000,
    max_tokens_out=16000,
    max_cost_usd=10.00,
)

VERY_HIGH_TIER = LimitTier(
    max_tool_calls_per_session=200,
    max_tokens_in=64000,
    max_tokens_out=32000,
    max_cost_usd=25.00,
)


@dataclass(frozen=True)
class PolicyPack:
    """Complete policy pack template."""

    name: str
    description: str
    scanners: ScannerConfig
    output_filtering: OutputFilteringConfig
    confirmation: ConfirmationConfig
    limit_tiers: dict[str, LimitTier] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to plain dict (for API responses)."""
        return {
            "name": self.name,
            "description": self.description,
            "scanners": {
                "injection_detection": self.scanners.injection_detection,
                "injection_threshold": self.scanners.injection_threshold,
                "pii_redaction": self.scanners.pii_redaction,
                "pii_mode": self.scanners.pii_mode,
                "secrets_scanning": self.scanners.secrets_scanning,
                "toxicity_detection": self.scanners.toxicity_detection,
                "toxicity_threshold": self.scanners.toxicity_threshold,
                "nemo_guardrails": self.scanners.nemo_guardrails,
            },
            "output_filtering": {
                "pii_redaction": self.output_filtering.pii_redaction,
                "secrets_scanning": self.output_filtering.secrets_scanning,
                "injection_detection": self.output_filtering.injection_detection,
                "max_output_size": self.output_filtering.max_output_size,
            },
            "confirmation": {
                "required_for_sensitivity": list(self.confirmation.required_for_sensitivity),
                "timeout_seconds": self.confirmation.timeout_seconds,
            },
            "limit_tiers": {
                tier_name: {
                    "max_tool_calls_per_session": tier.max_tool_calls_per_session,
                    "max_tokens_in": tier.max_tokens_in,
                    "max_tokens_out": tier.max_tokens_out,
                    "max_cost_usd": tier.max_cost_usd,
                }
                for tier_name, tier in self.limit_tiers.items()
            },
        }


# ═══════════════════════════════════════════════════════════════════════
# Built-in policy packs
# ═══════════════════════════════════════════════════════════════════════

_PACKS: dict[str, PolicyPack] = {
    "customer_support": PolicyPack(
        name="customer_support",
        description="Customer-facing support agent with strict injection and moderate toxicity controls",
        scanners=ScannerConfig(
            injection_detection=True,
            injection_threshold=0.3,
            pii_redaction=True,
            pii_mode="mask",
            secrets_scanning=True,
            toxicity_detection=True,
            toxicity_threshold=0.6,
            nemo_guardrails=True,
        ),
        output_filtering=OutputFilteringConfig(
            pii_redaction=True,
            secrets_scanning=True,
            injection_detection=True,
            max_output_size=4000,
        ),
        confirmation=ConfirmationConfig(
            required_for_sensitivity=("high", "critical"),
            timeout_seconds=300,
        ),
        limit_tiers={
            "low": LOW_TIER,
            "medium": MEDIUM_TIER,
            "high": HIGH_TIER,
        },
    ),
    "internal_copilot": PolicyPack(
        name="internal_copilot",
        description="Internal productivity assistant with moderate injection controls and high limits",
        scanners=ScannerConfig(
            injection_detection=True,
            injection_threshold=0.5,
            pii_redaction=True,
            pii_mode="log",
            secrets_scanning=True,
            toxicity_detection=True,
            toxicity_threshold=0.8,
            nemo_guardrails=True,
        ),
        output_filtering=OutputFilteringConfig(
            pii_redaction=True,
            secrets_scanning=True,
            injection_detection=True,
            max_output_size=8000,
        ),
        confirmation=ConfirmationConfig(
            required_for_sensitivity=("high", "critical"),
            timeout_seconds=600,
        ),
        limit_tiers={
            "low": MEDIUM_TIER,
            "medium": HIGH_TIER,
            "high": VERY_HIGH_TIER,
        },
    ),
    "finance": PolicyPack(
        name="finance",
        description="Financial operations agent with strict controls across all scanners",
        scanners=ScannerConfig(
            injection_detection=True,
            injection_threshold=0.2,
            pii_redaction=True,
            pii_mode="block",
            secrets_scanning=True,
            toxicity_detection=True,
            toxicity_threshold=0.4,
            nemo_guardrails=True,
        ),
        output_filtering=OutputFilteringConfig(
            pii_redaction=True,
            secrets_scanning=True,
            injection_detection=True,
            max_output_size=2000,
        ),
        confirmation=ConfirmationConfig(
            required_for_sensitivity=("medium", "high", "critical"),
            timeout_seconds=180,
        ),
        limit_tiers={
            "low": LOW_TIER,
            "medium": LOW_TIER,
            "high": MEDIUM_TIER,
        },
    ),
    "hr": PolicyPack(
        name="hr",
        description="HR agent handling employee data with strict PII and toxicity controls",
        scanners=ScannerConfig(
            injection_detection=True,
            injection_threshold=0.3,
            pii_redaction=True,
            pii_mode="block",
            secrets_scanning=True,
            toxicity_detection=True,
            toxicity_threshold=0.3,
            nemo_guardrails=True,
        ),
        output_filtering=OutputFilteringConfig(
            pii_redaction=True,
            secrets_scanning=True,
            injection_detection=True,
            max_output_size=2000,
        ),
        confirmation=ConfirmationConfig(
            required_for_sensitivity=("medium", "high", "critical"),
            timeout_seconds=180,
        ),
        limit_tiers={
            "low": LOW_TIER,
            "medium": LOW_TIER,
            "high": MEDIUM_TIER,
        },
    ),
    "research": PolicyPack(
        name="research",
        description="Research/experimentation agent with relaxed controls and very high limits",
        scanners=ScannerConfig(
            injection_detection=True,
            injection_threshold=0.7,
            pii_redaction=False,
            pii_mode="off",
            secrets_scanning=False,
            toxicity_detection=True,
            toxicity_threshold=0.9,
            nemo_guardrails=False,
        ),
        output_filtering=OutputFilteringConfig(
            pii_redaction=False,
            secrets_scanning=False,
            injection_detection=True,
            max_output_size=16000,
        ),
        confirmation=ConfirmationConfig(
            required_for_sensitivity=("critical",),
            timeout_seconds=600,
        ),
        limit_tiers={
            "low": HIGH_TIER,
            "medium": VERY_HIGH_TIER,
            "high": VERY_HIGH_TIER,
        },
    ),
}


def get_policy_pack(name: str) -> PolicyPack:
    """Get a policy pack by name. Raises KeyError if not found."""
    return _PACKS[name]


def list_policy_packs() -> list[PolicyPack]:
    """Return all available policy packs."""
    return list(_PACKS.values())


def get_policy_pack_dict(name: str) -> dict:
    """Get a policy pack as a plain dict (deep copy for safety)."""
    return copy.deepcopy(_PACKS[name].to_dict())
