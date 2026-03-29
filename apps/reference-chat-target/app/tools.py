"""Mock tools for the reference chat target."""

from __future__ import annotations

import secrets
from typing import Any

from app.retrieval import retrieve

# Tool definitions for the Gemini function-calling API
TOOL_DEFINITIONS = [
    {
        "name": "search_kb",
        "description": "Search the internal knowledge base for relevant articles.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_order_status",
        "description": "Look up the current status of a customer order by order ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "The order identifier, e.g. ORD-12345.",
                },
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "create_support_ticket_mock",
        "description": "Create a mock support ticket. This does not have real side effects.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short summary of the issue.",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of the issue.",
                },
            },
            "required": ["title", "description"],
        },
    },
]


def execute_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Execute a mock tool and return a result."""
    if name == "search_kb":
        docs = retrieve(arguments.get("query", ""), top_k=3)
        if not docs:
            return {"results": [], "message": "No relevant documents found."}
        return {
            "results": [
                {"id": d.id, "title": d.title, "snippet": d.body[:200]} for d in docs
            ],
        }
    if name == "get_order_status":
        order_id = arguments.get("order_id", "UNKNOWN")
        return {
            "order_id": order_id,
            "status": "shipped",
            "estimated_delivery": "2026-03-28",
            "tracking_number": "TRACK-" + secrets.token_hex(4).upper(),
        }
    if name == "create_support_ticket_mock":
        return {
            "ticket_id": "TKT-" + secrets.token_hex(4).upper(),
            "title": arguments.get("title", ""),
            "status": "created",
            "note": "This is a mock ticket. No real action was taken.",
        }
    return {"error": f"Unknown tool: {name}"}
