"""Mock tool implementations for test agents.

These tools return fake data.  The security layer (RBAC, limits, PII scanning)
is real — it comes from the wizard-generated integration kit that wraps these tools.

Tools return **JSON strings** (not dicts) to match how real tools return data
to LLM agents.  The PostToolGate scans this string for PII / injections.
"""

from __future__ import annotations

import json

from .mock_data import ORDERS, PRODUCTS, USERS


# ── Individual tool functions ────────────────────────────────────────


def get_orders(args: dict | None = None) -> str:
    """List all orders.  Access: read · Sensitivity: low."""
    return json.dumps({"orders": ORDERS, "total": len(ORDERS)}, indent=2)


def get_users(args: dict | None = None) -> str:
    """List all users.  Returns PII (emails, phones).  Access: read · Sensitivity: medium."""
    return json.dumps({"users": USERS, "total": len(USERS)}, indent=2)


def search_products(args: dict | None = None) -> str:
    """Search products by query.  Access: read · Sensitivity: low."""
    query = (args or {}).get("query", "").lower()
    if query:
        results = [
            p
            for p in PRODUCTS
            if query in p["name"].lower() or query in p["category"].lower()
        ]
    else:
        results = list(PRODUCTS)
    return json.dumps({"products": results, "total": len(results)}, indent=2)


def update_order(args: dict | None = None) -> str:
    """Update order status.  Access: write · Sensitivity: high · Admin only."""
    order_id = (args or {}).get("order_id", "unknown")
    new_status = (args or {}).get("status", "unknown")
    for order in ORDERS:
        if order["id"] == order_id:
            return json.dumps(
                {
                    "success": True,
                    "order_id": order_id,
                    "old_status": order["status"],
                    "new_status": new_status,
                    "message": f"Order {order_id} updated to '{new_status}'",
                }
            )
    return json.dumps({"success": False, "error": f"Order {order_id} not found"})


def update_user(args: dict | None = None) -> str:
    """Update user profile.  Access: write · Sensitivity: high · Admin only."""
    user_id = (args or {}).get("user_id", "unknown")
    updates = {k: v for k, v in (args or {}).items() if k != "user_id"}
    for user in USERS:
        if user["id"] == user_id:
            return json.dumps(
                {
                    "success": True,
                    "user_id": user_id,
                    "updated_fields": list(updates.keys()),
                    "message": f"User {user_id} profile updated",
                }
            )
    return json.dumps({"success": False, "error": f"User {user_id} not found"})


# ── Registry ─────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, callable] = {
    "getOrders": get_orders,
    "getUsers": get_users,
    "searchProducts": search_products,
    "updateOrder": update_order,
    "updateUser": update_user,
}


def execute_tool(tool_name: str, args: dict | None = None) -> str:
    """Execute a tool by name.  Returns a JSON string (always)."""
    fn = TOOL_REGISTRY.get(tool_name)
    if fn is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    return fn(args)
