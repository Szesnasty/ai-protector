# Step 02 — Shared Mock Tools

> **Effort:** 1 hour
> **Depends on:** nothing (pure Python, no DB)
> **Blocks:** steps 03, 04 (both agents import these tools)

---

## Context

Both test agents (Pure Python + LangGraph) need the same 5 tools with the same mock data.
Instead of duplicating, we create a shared module that both agents import.

---

## File Structure

```
apps/
  test-agents/
    shared/
      __init__.py
      tools.py          ← 5 tool functions with mock data
      mock_data.py       ← Fake orders, users, products
```

---

## Implementation Plan

### Step 1: Create `apps/test-agents/shared/mock_data.py`

Static data that tools return. Includes PII to test PostToolGate detection.

```python
"""Mock data for test agents. Includes deliberate PII for security gate testing."""

ORDERS = [
    {"id": "ORD-001", "customer": "Alice Johnson", "status": "shipped", "amount": 129.99, "items": ["Laptop Stand", "USB-C Hub"]},
    {"id": "ORD-002", "customer": "Bob Smith", "status": "pending", "amount": 49.50, "items": ["Wireless Mouse"]},
    {"id": "ORD-003", "customer": "Carol White", "status": "delivered", "amount": 299.00, "items": ["Monitor", "HDMI Cable"]},
    {"id": "ORD-004", "customer": "Dave Brown", "status": "processing", "amount": 15.99, "items": ["Phone Case"]},
    {"id": "ORD-005", "customer": "Eve Davis", "status": "cancelled", "amount": 89.00, "items": ["Keyboard"]},
]

# Deliberate PII: emails and phone numbers for PostToolGate to detect
USERS = [
    {"id": "USR-001", "name": "Alice Johnson", "email": "alice.johnson@acme.com", "phone": "+1-555-0101", "role": "customer"},
    {"id": "USR-002", "name": "Bob Smith", "email": "bob.smith@gmail.com", "phone": "+1-555-0102", "role": "customer"},
    {"id": "USR-003", "name": "Carol White", "email": "carol@internal.corp", "phone": "+1-555-0103", "role": "support"},
    {"id": "USR-004", "name": "Dave Brown", "email": "dave.brown@example.org", "phone": "+1-555-0104", "role": "admin"},
]

PRODUCTS = [
    {"id": "PROD-001", "name": "Laptop Stand", "price": 45.99, "category": "accessories", "in_stock": True},
    {"id": "PROD-002", "name": "USB-C Hub", "price": 29.99, "category": "accessories", "in_stock": True},
    {"id": "PROD-003", "name": "Wireless Mouse", "price": 24.50, "category": "peripherals", "in_stock": False},
    {"id": "PROD-004", "name": "Mechanical Keyboard", "price": 89.00, "category": "peripherals", "in_stock": True},
    {"id": "PROD-005", "name": "4K Monitor", "price": 299.00, "category": "displays", "in_stock": True},
    {"id": "PROD-006", "name": "HDMI Cable", "price": 12.99, "category": "cables", "in_stock": True},
]
```

### Step 2: Create `apps/test-agents/shared/tools.py`

5 tool functions. Each returns a dict with the result.

```python
"""Mock tool implementations for test agents.

These tools return fake data. The security layer (RBAC, limits, PII scanning)
is real — it comes from the wizard-generated integration kit.
"""

from __future__ import annotations
import json
from .mock_data import ORDERS, USERS, PRODUCTS


def get_orders(args: dict | None = None) -> str:
    """List all orders. Access: read, Sensitivity: low."""
    return json.dumps({"orders": ORDERS, "total": len(ORDERS)}, indent=2)


def get_users(args: dict | None = None) -> str:
    """List all users. Returns PII (emails, phones). Access: read, Sensitivity: medium."""
    return json.dumps({"users": USERS, "total": len(USERS)}, indent=2)


def search_products(args: dict | None = None) -> str:
    """Search products by query. Access: read, Sensitivity: low."""
    query = (args or {}).get("query", "").lower()
    if query:
        results = [p for p in PRODUCTS if query in p["name"].lower() or query in p["category"].lower()]
    else:
        results = PRODUCTS
    return json.dumps({"products": results, "total": len(results)}, indent=2)


def update_order(args: dict | None = None) -> str:
    """Update order status. Access: write, Sensitivity: high. Admin only."""
    order_id = (args or {}).get("order_id", "unknown")
    new_status = (args or {}).get("status", "unknown")
    # Find and "update" (mock)
    for order in ORDERS:
        if order["id"] == order_id:
            return json.dumps({
                "success": True,
                "order_id": order_id,
                "old_status": order["status"],
                "new_status": new_status,
                "message": f"Order {order_id} updated to '{new_status}'",
            })
    return json.dumps({"success": False, "error": f"Order {order_id} not found"})


def update_user(args: dict | None = None) -> str:
    """Update user profile. Access: write, Sensitivity: high. Admin only."""
    user_id = (args or {}).get("user_id", "unknown")
    updates = {k: v for k, v in (args or {}).items() if k != "user_id"}
    for user in USERS:
        if user["id"] == user_id:
            return json.dumps({
                "success": True,
                "user_id": user_id,
                "updated_fields": list(updates.keys()),
                "message": f"User {user_id} profile updated",
            })
    return json.dumps({"success": False, "error": f"User {user_id} not found"})


# Registry: tool name → function mapping
TOOL_REGISTRY: dict[str, callable] = {
    "getOrders": get_orders,
    "getUsers": get_users,
    "searchProducts": search_products,
    "updateOrder": update_order,
    "updateUser": update_user,
}


def execute_tool(tool_name: str, args: dict | None = None) -> str:
    """Execute a tool by name. Returns JSON string."""
    fn = TOOL_REGISTRY.get(tool_name)
    if fn is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    return fn(args)
```

### Step 3: Create `apps/test-agents/shared/__init__.py`

```python
from .tools import TOOL_REGISTRY, execute_tool
from .mock_data import ORDERS, USERS, PRODUCTS

__all__ = ["TOOL_REGISTRY", "execute_tool", "ORDERS", "USERS", "PRODUCTS"]
```

---

## Key Design Decisions

1. **PII in mock data is deliberate** — `USERS` contains emails and phone numbers so the
   PostToolGate's PII scanner has something to detect.

2. **Tools return JSON strings** (not dicts) — this matches how real tools return data
   to LLM agents. The PostToolGate scans this string.

3. **`execute_tool(name, args)`** is the universal entry point — both agents use it,
   regardless of whether they're Pure Python or LangGraph.

4. **No security logic here** — tools are pure data. All security (RBAC, limits, PII scan)
   lives in the wizard-generated code that wraps these tools.

---

## Definition of Done

- [ ] `apps/test-agents/shared/` directory exists with 3 files
- [ ] `mock_data.py` has ORDERS (5), USERS (4 with PII), PRODUCTS (6)
- [ ] `tools.py` has 5 functions + TOOL_REGISTRY + `execute_tool()`
- [ ] `from shared.tools import execute_tool` works
- [ ] `execute_tool("getOrders")` returns valid JSON with 5 orders
- [ ] `execute_tool("getUsers")` returns JSON containing email addresses (for PII gate testing)
- [ ] `execute_tool("searchProducts", {"query": "monitor"})` filters correctly
- [ ] `execute_tool("updateOrder", {"order_id": "ORD-001", "status": "shipped"})` returns success
- [ ] `execute_tool("unknownTool")` returns error JSON (not an exception)
