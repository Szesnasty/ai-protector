"""OpenAI function-calling tool definitions for LLM mode.

LiteLLM handles the conversion for all providers (Anthropic, Google, etc.)
so we only need the OpenAI format.

These definitions tell the LLM what tools are available, what arguments
they accept, and when to call them.
"""

from __future__ import annotations

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "getOrders",
            "description": "List all customer orders with status and amounts.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "getUsers",
            "description": "List all users. Returns PII (emails, phone numbers).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "searchProducts",
            "description": "Search products by name or category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to filter products by name or category",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "updateOrder",
            "description": "Update an order's status. Requires admin role.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID to update (e.g. ORD-001)",
                    },
                    "status": {
                        "type": "string",
                        "enum": [
                            "pending",
                            "processing",
                            "shipped",
                            "delivered",
                            "cancelled",
                        ],
                        "description": "The new order status",
                    },
                },
                "required": ["order_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "updateUser",
            "description": "Update a user's profile information. Requires admin role.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user ID to update (e.g. USR-001)",
                    },
                    "name": {"type": "string", "description": "New display name"},
                    "email": {"type": "string", "description": "New email address"},
                },
                "required": ["user_id"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "You are a helpful customer-service assistant for an e-commerce store. "
    "You have access to tools for looking up orders, users, and products, "
    "as well as updating orders and user profiles. "
    "Use the tools to answer user questions accurately. "
    "Only call tools when you need real data — do not make up information. "
    "If a tool call is denied by the security layer, explain the restriction "
    "to the user politely without revealing internal details."
)
