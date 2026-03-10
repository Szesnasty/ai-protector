"""Seed data for the Agent Wizard."""

import structlog
from sqlalchemy import select

from src.db.session import async_session
from src.wizard.models import (
    AccessType,
    Agent,
    AgentEnvironment,
    AgentFramework,
    AgentRole,
    AgentStatus,
    AgentTool,
    RoleToolPermission,
    RolloutMode,
    Sensitivity,
)
from src.wizard.services.risk import apply_risk_classification
from src.wizard.services.tools import apply_smart_defaults

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

# ── Reference tools (matches rbac_config.yaml) ──────────────────────────

REFERENCE_TOOLS = [
    {
        "name": "searchKnowledgeBase",
        "description": "Search product documentation and FAQ",
        "category": "knowledge",
        "access_type": AccessType.READ,
        "sensitivity": Sensitivity.LOW,
        "returns_pii": False,
        "returns_secrets": False,
    },
    {
        "name": "getOrderStatus",
        "description": "Retrieve order status by order ID",
        "category": "orders",
        "access_type": AccessType.READ,
        "sensitivity": Sensitivity.LOW,
        "returns_pii": False,
        "returns_secrets": False,
    },
    {
        "name": "getCustomerProfile",
        "description": "Retrieve customer profile with personal data",
        "category": "customers",
        "access_type": AccessType.READ,
        "sensitivity": Sensitivity.MEDIUM,
        "returns_pii": True,
        "returns_secrets": False,
    },
    {
        "name": "issueRefund",
        "description": "Process a refund for a customer order",
        "category": "orders",
        "access_type": AccessType.WRITE,
        "sensitivity": Sensitivity.HIGH,
        "returns_pii": False,
        "returns_secrets": False,
    },
    {
        "name": "getInternalSecrets",
        "description": "Access internal configuration secrets (admin only)",
        "category": "admin",
        "access_type": AccessType.READ,
        "sensitivity": Sensitivity.CRITICAL,
        "returns_pii": False,
        "returns_secrets": True,
    },
]

# ── Reference roles (matches rbac_config.yaml inheritance chain) ────────

REFERENCE_ROLES = [
    {"name": "customer", "description": "End-user customer role", "inherits_from": None},
    {"name": "support", "description": "Support agent role", "inherits_from": "customer"},
    {"name": "admin", "description": "Administrative role", "inherits_from": "support"},
]

# ── Permission assignments per role (own, not inherited) ────────────────

REFERENCE_PERMISSIONS: dict[str, list[str]] = {
    "customer": ["searchKnowledgeBase", "getOrderStatus"],
    "support": ["getCustomerProfile"],
    "admin": ["issueRefund", "getInternalSecrets"],
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


async def seed_reference_tools_and_roles() -> None:
    """Seed tools, roles, and permissions for the reference agent (idempotent)."""
    async with async_session() as session:
        # Find reference agent
        result = await session.execute(select(Agent).where(Agent.name == REFERENCE_AGENT["name"]))
        agent = result.scalar_one_or_none()
        if agent is None:
            logger.warning("seed_tools_roles_skipped", reason="reference agent not found")
            return

        # Check if tools already exist
        tools_result = await session.execute(select(AgentTool).where(AgentTool.agent_id == agent.id))
        if tools_result.scalars().first() is not None:
            logger.debug("seed_tools_roles_exists", agent=agent.name)
            return

        # ── Create tools ────────────────────────────────────────────
        tool_map: dict[str, AgentTool] = {}
        for tool_data in REFERENCE_TOOLS:
            tool = AgentTool(agent_id=agent.id, **tool_data)
            apply_smart_defaults(tool)
            session.add(tool)
            tool_map[tool.name] = tool

        await session.flush()  # assign IDs

        # ── Create roles (order matters for inheritance) ────────────
        role_map: dict[str, AgentRole] = {}
        for role_data in REFERENCE_ROLES:
            parent_name = role_data["inherits_from"]
            inherits_from = role_map[parent_name].id if parent_name else None
            role = AgentRole(
                agent_id=agent.id,
                name=role_data["name"],
                description=role_data["description"],
                inherits_from=inherits_from,
            )
            session.add(role)
            await session.flush()  # assign ID for next role's parent ref
            role_map[role.name] = role

        # ── Assign permissions ──────────────────────────────────────
        for role_name, tool_names in REFERENCE_PERMISSIONS.items():
            role = role_map[role_name]
            for tool_name in tool_names:
                tool = tool_map[tool_name]
                perm = RoleToolPermission(
                    role_id=role.id,
                    tool_id=tool.id,
                    scopes=["read"] if tool.access_type == AccessType.READ else ["read", "write"],
                )
                session.add(perm)

        await session.commit()
        logger.info(
            "seed_tools_roles_created",
            agent=agent.name,
            tools=len(REFERENCE_TOOLS),
            roles=len(REFERENCE_ROLES),
        )


async def seed_wizard() -> None:
    """Run all wizard seed functions."""
    await seed_reference_agent()
    await seed_reference_tools_and_roles()
