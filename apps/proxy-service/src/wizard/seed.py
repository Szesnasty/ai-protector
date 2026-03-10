"""Seed data for the Agent Wizard."""

import structlog
from sqlalchemy import select

from src.db.session import async_session
from src.wizard.models import (
    Agent,
    AgentEnvironment,
    AgentFramework,
    AgentStatus,
    RolloutMode,
)
from src.wizard.services.risk import apply_risk_classification

logger = structlog.get_logger()

REFERENCE_AGENT = {
    "name": "Customer Support Copilot",
    "description": (
        "AI-powered customer support agent that handles product inquiries, "
        "order lookups, and refund processing. Uses tool calls for knowledge "
        "base search, order status retrieval, and administrative actions."
    ),
    "team": "support",
    "framework": AgentFramework.LANGGRAPH,
    "environment": AgentEnvironment.PRODUCTION,
    "is_public_facing": True,
    "has_tools": True,
    "has_write_actions": True,
    "touches_pii": True,
    "handles_secrets": False,
    "calls_external_apis": False,
    "status": AgentStatus.ACTIVE,
    "is_reference": True,
    "rollout_mode": RolloutMode.ENFORCE,
}


async def seed_reference_agent() -> None:
    """Insert the reference agent if it doesn't exist (idempotent)."""
    async with async_session() as session:
        stmt = select(Agent).where(Agent.name == REFERENCE_AGENT["name"])
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            agent = Agent(**REFERENCE_AGENT)
            apply_risk_classification(agent)
            session.add(agent)
            await session.commit()
            logger.info(
                "seed_reference_agent_created",
                name=agent.name,
                risk=agent.risk_level,
                protection=agent.protection_level,
            )
        else:
            logger.debug("seed_reference_agent_exists", name=existing.name)


async def seed_wizard() -> None:
    """Run all wizard seed functions."""
    await seed_reference_agent()
