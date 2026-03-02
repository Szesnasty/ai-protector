"""Seed default firewall policies."""

import structlog
from sqlalchemy import select

from src.db.session import async_session
from src.models.policy import Policy

logger = structlog.get_logger()

DEFAULT_POLICIES = [
    {
        "name": "fast",
        "description": "Minimal checks — rules only. High throughput, trusted clients.",
        "config": {
            "nodes": ["parse", "intent", "rules", "decision", "llm", "basic_output", "logging"],
            "thresholds": {"max_risk": 0.9},
        },
    },
    {
        "name": "balanced",
        "description": "Default — rules + LLM Guard + output filter + memory hygiene.",
        "config": {
            "nodes": [
                "parse", "intent", "rules", "llm_guard", "decision",
                "transform", "llm", "output_filter", "memory_hygiene", "logging",
            ],
            "thresholds": {"max_risk": 0.7, "injection_threshold": 0.5},
        },
    },
    {
        "name": "strict",
        "description": "Full pipeline — adds Presidio PII + ML Judge.",
        "config": {
            "nodes": [
                "parse", "intent", "rules", "llm_guard", "presidio", "ml_judge",
                "decision", "transform", "llm", "output_filter", "memory_hygiene", "logging",
            ],
            "thresholds": {"max_risk": 0.5, "injection_threshold": 0.3, "pii_action": "mask"},
        },
    },
    {
        "name": "paranoid",
        "description": "Maximum security — canary tokens + full audit logging.",
        "config": {
            "nodes": [
                "parse", "intent", "rules", "llm_guard", "presidio", "ml_judge",
                "decision", "canary", "transform", "llm", "output_filter", "memory_hygiene", "logging",
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
                logger.debug("seed_policy_exists", name=policy_data["name"])

        await session.commit()
    logger.info("seed_policies_done", count=len(DEFAULT_POLICIES))
