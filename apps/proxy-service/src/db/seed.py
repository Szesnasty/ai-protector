"""Seed default firewall policies and denylist phrases."""

import structlog
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.db.session import async_session
from src.models.denylist import DenylistPhrase
from src.models.policy import Policy

logger = structlog.get_logger()

DEFAULT_POLICIES = [
    {
        "name": "fast",
        "description": "Minimal checks — rules only. High throughput, trusted clients.",
        "config": {
            "nodes": [],
            "thresholds": {"max_risk": 0.9},
        },
    },
    {
        "name": "balanced",
        "description": "Default — rules + LLM Guard + output filter + memory hygiene.",
        "config": {
            "nodes": ["llm_guard", "output_filter", "memory_hygiene", "logging"],
            "thresholds": {"max_risk": 0.7, "injection_threshold": 0.5},
        },
    },
    {
        "name": "strict",
        "description": "Full pipeline — adds Presidio PII + ML Judge.",
        "config": {
            "nodes": [
                "llm_guard", "presidio", "ml_judge",
                "output_filter", "memory_hygiene", "logging",
            ],
            "thresholds": {"max_risk": 0.5, "injection_threshold": 0.3, "pii_action": "mask"},
        },
    },
    {
        "name": "paranoid",
        "description": "Maximum security — canary tokens + full audit logging.",
        "config": {
            "nodes": [
                "llm_guard", "presidio", "ml_judge",
                "canary", "output_filter", "memory_hygiene", "logging",
            ],
            "thresholds": {
                "max_risk": 0.3,
                "injection_threshold": 0.2,
                "pii_action": "block",
                "enable_canary": True,
            },
        },
    },
]


async def seed_policies() -> None:
    """Insert default policies if they don't exist (idempotent upsert by name)."""
    async with async_session() as session:
        for policy_data in DEFAULT_POLICIES:
            stmt = select(Policy).where(Policy.name == policy_data["name"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is None:
                policy = Policy(**policy_data)
                session.add(policy)
                logger.info("seed_policy_created", name=policy_data["name"])
            else:
                # Update config to latest seed definition
                if existing.config != policy_data["config"]:
                    existing.config = policy_data["config"]
                    logger.info("seed_policy_config_updated", name=policy_data["name"])
                else:
                    logger.debug("seed_policy_exists", name=policy_data["name"])

        await session.commit()
    logger.info("seed_policies_done", count=len(DEFAULT_POLICIES))


# ── Denylist phrases ──────────────────────────────────────────────────

DEFAULT_DENYLIST: list[dict] = [
    # Injection
    {"phrase": "ignore previous instructions", "category": "injection", "is_regex": False},
    {"phrase": "ignore all prior", "category": "injection", "is_regex": False},
    # Jailbreak
    {"phrase": "you are now", "category": "jailbreak", "is_regex": False},
    {"phrase": "pretend you are", "category": "jailbreak", "is_regex": False},
    {"phrase": r"(?i)act\s+as\s+(DAN|evil|unfiltered)", "category": "jailbreak", "is_regex": True},
    # Extraction
    {"phrase": "reveal your system prompt", "category": "extraction", "is_regex": False},
    {"phrase": "repeat the above", "category": "extraction", "is_regex": False},
    # Harmful
    {"phrase": r"(?i)\b(bomb|weapon|exploit)\b.*\b(make|build|create)\b", "category": "harmful", "is_regex": True},
]

# Policies that get denylist phrases (not "fast")
DENYLIST_POLICY_NAMES = ["balanced", "strict", "paranoid"]


async def seed_denylist() -> None:
    """Seed default denylist phrases linked to non-fast policies (idempotent)."""
    async with async_session() as session:
        created = 0
        for policy_name in DENYLIST_POLICY_NAMES:
            stmt = (
                select(Policy)
                .where(Policy.name == policy_name)
                .options(joinedload(Policy.denylist_phrases))
            )
            result = await session.execute(stmt)
            policy = result.unique().scalar_one_or_none()
            if policy is None:
                logger.warning("seed_denylist_policy_not_found", policy=policy_name)
                continue

            existing_phrases = {dp.phrase for dp in policy.denylist_phrases}
            for entry in DEFAULT_DENYLIST:
                if entry["phrase"] in existing_phrases:
                    continue
                dp = DenylistPhrase(
                    policy_id=policy.id,
                    phrase=entry["phrase"],
                    category=entry["category"],
                    is_regex=entry.get("is_regex", False),
                )
                session.add(dp)
                created += 1

        await session.commit()
    logger.info("seed_denylist_done", created=created)
