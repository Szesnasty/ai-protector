"""PolicyCheckNode — RBAC: filter tools by user_role."""

from __future__ import annotations

import structlog

from src.agent.state import AgentState
from src.agent.tools.registry import get_allowed_tools

logger = structlog.get_logger()


def policy_check_node(state: AgentState) -> AgentState:
    """Determine which tools the user is allowed to use based on role."""
    user_role = state.get("user_role", "customer")
    allowed = get_allowed_tools(user_role)

    logger.info("policy_check_node", user_role=user_role, allowed_tools=allowed)

    return {
        **state,
        "allowed_tools": allowed,
    }
