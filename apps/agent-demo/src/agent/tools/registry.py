"""Tool registry — RBAC configuration and tool dispatch."""

from __future__ import annotations

from typing import Any, Callable

from src.agent.tools.kb import search_knowledge_base
from src.agent.tools.orders import get_order_status
from src.agent.tools.secrets import get_internal_secrets

# Tool name → callable mapping
TOOL_FUNCTIONS: dict[str, Callable[..., str]] = {
    "searchKnowledgeBase": search_knowledge_base,
    "getOrderStatus": get_order_status,
    "getInternalSecrets": get_internal_secrets,
}

# Tool descriptions for LLM system prompt
TOOL_DESCRIPTIONS: dict[str, str] = {
    "searchKnowledgeBase": "Search the knowledge base / FAQ for information. Args: query (string).",
    "getOrderStatus": "Look up order status by order ID. Args: order_id (string).",
    "getInternalSecrets": "Retrieve internal API keys and configuration. No args needed.",
}

# Role → allowed tool names
ROLE_TOOLS: dict[str, list[str]] = {
    "customer": ["searchKnowledgeBase", "getOrderStatus"],
    "admin": ["searchKnowledgeBase", "getOrderStatus", "getInternalSecrets"],
}


def get_allowed_tools(user_role: str) -> list[str]:
    """Return list of tool names allowed for the given role."""
    return ROLE_TOOLS.get(user_role, [])


def execute_tool(tool_name: str, args: dict[str, Any]) -> str:
    """Execute a tool by name with given args. Raises KeyError if unknown."""
    fn = TOOL_FUNCTIONS[tool_name]
    return fn(**args)


def get_tools_description(allowed_tools: list[str]) -> str:
    """Build a tool description string for the LLM system prompt."""
    lines = []
    for name in allowed_tools:
        desc = TOOL_DESCRIPTIONS.get(name, "No description.")
        lines.append(f"- {name}: {desc}")
    return "\n".join(lines)
