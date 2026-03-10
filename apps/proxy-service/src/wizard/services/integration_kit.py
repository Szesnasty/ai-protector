"""Integration kit generator (spec 29).

Builds a 7-file deployment kit from Jinja2 templates + existing YAML generators.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

import jinja2
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value

from src.wizard.models import Agent, AgentRole, AgentTool, RoleToolPermission
from src.wizard.services.config_gen import (
    generate_limits_yaml,
    generate_policy_yaml,
    generate_rbac_yaml,
)
from src.wizard.services.policy_packs import get_policy_pack

# ── Jinja2 environment ──────────────────────────────────────────────────

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "kit"

_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATE_DIR)),
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=jinja2.StrictUndefined,
)


def get_jinja_env() -> jinja2.Environment:
    """Return the configured Jinja2 environment."""
    return _jinja_env


# ── Context builder ─────────────────────────────────────────────────────


async def build_kit_context(agent_id: uuid.UUID, db: AsyncSession) -> dict:
    """Build the template context dict from DB state.

    Raises ValueError if agent not found.
    """
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise ValueError(f"Agent {agent_id} not found")

    # Load tools
    result = await db.execute(select(AgentTool).where(AgentTool.agent_id == agent_id).order_by(AgentTool.name))
    tools = list(result.scalars().all())

    # Load roles with permissions + parent chain
    result = await db.execute(
        select(AgentRole)
        .where(AgentRole.agent_id == agent_id)
        .options(
            selectinload(AgentRole.permissions).selectinload(RoleToolPermission.tool),
        )
        .order_by(AgentRole.name)
    )
    roles = list(result.scalars().unique().all())
    role_by_id = {r.id: r for r in roles}
    for role in roles:
        parent = role_by_id.get(role.inherits_from) if role.inherits_from else None
        set_committed_value(role, "parent", parent)

    # Sort roles by depth (base first)
    def _depth(r: AgentRole, visited: set | None = None) -> int:
        if visited is None:
            visited = set()
        if r.id in visited:
            return 0
        visited.add(r.id)
        if r.parent is None:
            return 0
        return _depth(r.parent, visited) + 1

    sorted_roles = sorted(roles, key=lambda r: (_depth(r), r.name))

    pack_name = agent.policy_pack or "customer_support"
    try:
        pack = get_policy_pack(pack_name)
        pack_config = pack.to_dict()
    except KeyError:
        pack = get_policy_pack("customer_support")
        pack_config = pack.to_dict()
        pack_name = "customer_support"

    tools_list = [
        {
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "access_type": t.access_type.value,
            "sensitivity": t.sensitivity.value,
            "requires_confirmation": t.requires_confirmation,
            "rate_limit": t.rate_limit,
            "returns_pii": t.returns_pii,
            "returns_secrets": t.returns_secrets,
        }
        for t in tools
    ]

    roles_list = [
        {
            "name": r.name,
            "description": r.description,
            "inherits_from": r.parent.name if r.parent else None,
            "own_tools": [
                {
                    "name": p.tool.name,
                    "scopes": p.scopes,
                    "sensitivity": p.tool.sensitivity.value,
                    "requires_confirmation": p.tool.requires_confirmation,
                }
                for p in r.permissions
                if p.tool is not None
            ],
        }
        for r in sorted_roles
    ]

    return {
        "agent_name": agent.name,
        "agent_id": str(agent.id),
        "agent_description": agent.description,
        "framework": agent.framework.value,
        "environment": agent.environment.value,
        "risk_level": agent.risk_level.value if agent.risk_level else "unknown",
        "protection_level": agent.protection_level.value if agent.protection_level else "unknown",
        "rollout_mode": agent.rollout_mode.value,
        "tools": tools_list,
        "roles": roles_list,
        "policy_pack": pack_name,
        "pack_config": pack_config,
        "proxy_url": "http://localhost:8000",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# ── Kit generation ──────────────────────────────────────────────────────

_FRAMEWORK_TEMPLATE = {
    "langgraph": "langgraph_protection.py.j2",
    "raw_python": "raw_python_protection.py.j2",
    "proxy_only": "proxy_only.py.j2",
}


def _slugify(name: str) -> str:
    """Slugify agent name for filenames."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


async def generate_integration_kit(
    agent_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """Generate all 7 kit files.

    Returns dict with keys:
      files: {filename: content_string}
      framework: str
      generated_at: str
    """
    ctx = await build_kit_context(agent_id, db)
    env = get_jinja_env()

    # 1-3: YAML files from existing generators (byte-identical to spec 28)
    rbac_yaml = await generate_rbac_yaml(agent_id, db)
    limits_yaml = await generate_limits_yaml(agent_id, db)
    policy_yaml = await generate_policy_yaml(agent_id, db)

    # 4: protected_agent.py (framework-specific)
    framework = ctx["framework"]
    template_name = _FRAMEWORK_TEMPLATE.get(framework, "langgraph_protection.py.j2")
    protected_agent = env.get_template(template_name).render(ctx)

    # 5: .env.protector
    env_protector = env.get_template("env.protector.j2").render(ctx)

    # 6: test_security.py
    test_security = env.get_template("test_security.py.j2").render(ctx)

    # 7: README.md
    readme = env.get_template("README.md.j2").render(ctx)

    generated_at = ctx["generated_at"]

    return {
        "files": {
            "rbac.yaml": rbac_yaml,
            "limits.yaml": limits_yaml,
            "policy.yaml": policy_yaml,
            "protected_agent.py": protected_agent,
            ".env.protector": env_protector,
            "test_security.py": test_security,
            "README.md": readme,
        },
        "framework": framework,
        "generated_at": generated_at,
    }
