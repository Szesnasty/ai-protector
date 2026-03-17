"""Comprehensive tests for apps/test-agents/shared/ module.

Covers every DoD item from 02-shared-mock-tools.md plus additional
edge-case and structural tests.
"""

from __future__ import annotations

import json

import pytest

# ── We need the shared package importable ────────────────────────────
# Tests are run from apps/test-agents/ so `shared` is a direct import.
from shared import (
    ORDERS,
    PRODUCTS,
    SYSTEM_PROMPT,
    TOOL_DEFINITIONS,
    TOOL_REGISTRY,
    USERS,
    execute_tool,
)
from shared.tool_definitions import TOOL_DEFINITIONS as TD_DIRECT
from shared.tools import (
    get_orders,
    get_users,
    search_products,
    update_order,
    update_user,
)


# ═══════════════════════════════════════════════════════════════════════
# 1. Mock Data — structural checks
# ═══════════════════════════════════════════════════════════════════════


class TestMockDataStructure:
    """Verify mock data lists have correct counts and shapes."""

    def test_orders_count(self):
        """ORDERS has exactly 5 items."""
        assert len(ORDERS) == 5

    def test_users_count(self):
        """USERS has exactly 4 items."""
        assert len(USERS) == 4

    def test_products_count(self):
        """PRODUCTS has exactly 6 items."""
        assert len(PRODUCTS) == 6

    def test_orders_have_required_keys(self):
        """Every order has id, customer, status, amount, items."""
        required = {"id", "customer", "status", "amount", "items"}
        for order in ORDERS:
            assert required.issubset(order.keys()), (
                f"Order {order.get('id')} missing keys"
            )

    def test_users_have_required_keys(self):
        """Every user has id, name, email, phone, role."""
        required = {"id", "name", "email", "phone", "role"}
        for user in USERS:
            assert required.issubset(user.keys()), f"User {user.get('id')} missing keys"

    def test_products_have_required_keys(self):
        """Every product has id, name, price, category, in_stock."""
        required = {"id", "name", "price", "category", "in_stock"}
        for product in PRODUCTS:
            assert required.issubset(product.keys()), (
                f"Product {product.get('id')} missing keys"
            )


# ═══════════════════════════════════════════════════════════════════════
# 2. PII in mock data (deliberate — for PostToolGate testing)
# ═══════════════════════════════════════════════════════════════════════


class TestPIIPresence:
    """Ensure PII exists in user data so the PII scanner has something to find."""

    def test_users_contain_emails(self):
        """Every user has an email containing '@'."""
        for user in USERS:
            assert "@" in user["email"], f"User {user['id']} has no email"

    def test_users_contain_phone_numbers(self):
        """Every user has a phone number starting with '+'."""
        for user in USERS:
            assert user["phone"].startswith("+"), f"User {user['id']} has no phone"

    def test_get_users_output_contains_email(self):
        """getUsers JSON output contains email addresses."""
        result = get_users()
        assert "@" in result, (
            "getUsers output should contain email addresses for PII gate"
        )

    def test_get_users_output_contains_phone(self):
        """getUsers JSON output contains phone numbers."""
        result = get_users()
        assert "+1-555" in result, (
            "getUsers output should contain phone numbers for PII gate"
        )


# ═══════════════════════════════════════════════════════════════════════
# 3. Individual tool functions
# ═══════════════════════════════════════════════════════════════════════


class TestGetOrders:
    """getOrders tool."""

    def test_returns_valid_json(self):
        result = json.loads(get_orders())
        assert "orders" in result
        assert "total" in result

    def test_returns_5_orders(self):
        result = json.loads(get_orders())
        assert result["total"] == 5
        assert len(result["orders"]) == 5

    def test_accepts_none_args(self):
        """Works with args=None (default)."""
        result = json.loads(get_orders(None))
        assert result["total"] == 5

    def test_accepts_empty_dict(self):
        """Works with empty dict args."""
        result = json.loads(get_orders({}))
        assert result["total"] == 5


class TestGetUsers:
    """getUsers tool."""

    def test_returns_valid_json(self):
        result = json.loads(get_users())
        assert "users" in result
        assert "total" in result

    def test_returns_4_users(self):
        result = json.loads(get_users())
        assert result["total"] == 4
        assert len(result["users"]) == 4


class TestSearchProducts:
    """searchProducts tool."""

    def test_no_query_returns_all(self):
        """No query → returns all 6 products."""
        result = json.loads(search_products())
        assert result["total"] == 6

    def test_empty_query_returns_all(self):
        """Empty string query → returns all 6 products."""
        result = json.loads(search_products({"query": ""}))
        assert result["total"] == 6

    def test_query_by_name(self):
        """'monitor' matches the 4K Monitor."""
        result = json.loads(search_products({"query": "monitor"}))
        assert result["total"] == 1
        assert result["products"][0]["name"] == "4K Monitor"

    def test_query_by_category(self):
        """'accessories' matches Laptop Stand and USB-C Hub."""
        result = json.loads(search_products({"query": "accessories"}))
        assert result["total"] == 2

    def test_query_case_insensitive(self):
        """Search is case-insensitive."""
        result = json.loads(search_products({"query": "MONITOR"}))
        assert result["total"] == 1

    def test_query_no_match(self):
        """Non-matching query returns empty list."""
        result = json.loads(search_products({"query": "zzzzz"}))
        assert result["total"] == 0
        assert result["products"] == []

    def test_query_peripherals(self):
        """'peripherals' matches 2 products."""
        result = json.loads(search_products({"query": "peripherals"}))
        assert result["total"] == 2


class TestUpdateOrder:
    """updateOrder tool."""

    def test_existing_order_success(self):
        result = json.loads(
            update_order({"order_id": "ORD-001", "status": "delivered"})
        )
        assert result["success"] is True
        assert result["order_id"] == "ORD-001"
        assert result["new_status"] == "delivered"
        assert "old_status" in result

    def test_nonexistent_order_failure(self):
        result = json.loads(update_order({"order_id": "ORD-999", "status": "shipped"}))
        assert result["success"] is False
        assert "error" in result

    def test_no_args_defaults(self):
        """No args → order_id='unknown', graceful failure."""
        result = json.loads(update_order())
        assert result["success"] is False

    def test_each_order_updatable(self):
        """Every order in ORDERS can be updated."""
        for order in ORDERS:
            result = json.loads(
                update_order({"order_id": order["id"], "status": "test"})
            )
            assert result["success"] is True, f"Failed to update {order['id']}"


class TestUpdateUser:
    """updateUser tool."""

    def test_existing_user_success(self):
        result = json.loads(update_user({"user_id": "USR-001", "name": "New Name"}))
        assert result["success"] is True
        assert result["user_id"] == "USR-001"
        assert "name" in result["updated_fields"]

    def test_nonexistent_user_failure(self):
        result = json.loads(update_user({"user_id": "USR-999"}))
        assert result["success"] is False
        assert "error" in result

    def test_no_args_defaults(self):
        result = json.loads(update_user())
        assert result["success"] is False

    def test_multiple_fields_update(self):
        result = json.loads(
            update_user({"user_id": "USR-002", "name": "X", "email": "x@y.z"})
        )
        assert result["success"] is True
        assert set(result["updated_fields"]) == {"name", "email"}


# ═══════════════════════════════════════════════════════════════════════
# 4. Tool Registry & execute_tool
# ═══════════════════════════════════════════════════════════════════════


class TestToolRegistry:
    """TOOL_REGISTRY and execute_tool()."""

    def test_registry_has_5_tools(self):
        assert len(TOOL_REGISTRY) == 5

    EXPECTED_TOOLS = [
        "getOrders",
        "getUsers",
        "searchProducts",
        "updateOrder",
        "updateUser",
    ]

    @pytest.mark.parametrize("tool_name", EXPECTED_TOOLS)
    def test_registry_contains_tool(self, tool_name: str):
        assert tool_name in TOOL_REGISTRY

    @pytest.mark.parametrize("tool_name", EXPECTED_TOOLS)
    def test_registry_values_are_callable(self, tool_name: str):
        assert callable(TOOL_REGISTRY[tool_name])

    def test_execute_tool_get_orders(self):
        """DoD: execute_tool('getOrders') returns valid JSON with 5 orders."""
        result = json.loads(execute_tool("getOrders"))
        assert result["total"] == 5

    def test_execute_tool_get_users(self):
        """DoD: execute_tool('getUsers') returns JSON with email addresses."""
        raw = execute_tool("getUsers")
        assert "@" in raw  # PII present
        result = json.loads(raw)
        assert result["total"] == 4

    def test_execute_tool_search_products_filter(self):
        """DoD: execute_tool('searchProducts', {'query': 'monitor'}) filters correctly."""
        result = json.loads(execute_tool("searchProducts", {"query": "monitor"}))
        assert result["total"] == 1

    def test_execute_tool_update_order(self):
        """DoD: execute_tool('updateOrder', ...) returns success."""
        result = json.loads(
            execute_tool("updateOrder", {"order_id": "ORD-001", "status": "shipped"})
        )
        assert result["success"] is True

    def test_execute_tool_unknown_returns_error_json(self):
        """DoD: execute_tool('unknownTool') returns error JSON, no exception."""
        raw = execute_tool("unknownTool")
        result = json.loads(raw)
        assert "error" in result
        assert "unknownTool" in result["error"]

    def test_execute_tool_unknown_does_not_raise(self):
        """Unknown tool returns error dict, never raises."""
        try:
            execute_tool("nonexistent", {"a": 1})
        except Exception as exc:
            pytest.fail(f"execute_tool should not raise, got {exc!r}")


# ═══════════════════════════════════════════════════════════════════════
# 5. Tool Definitions (OpenAI function-calling format)
# ═══════════════════════════════════════════════════════════════════════


class TestToolDefinitions:
    """TOOL_DEFINITIONS for LLM mode."""

    def test_has_5_definitions(self):
        assert len(TOOL_DEFINITIONS) == 5

    def test_direct_import_matches_init(self):
        """Both import paths return the same object."""
        assert TOOL_DEFINITIONS is TD_DIRECT

    @pytest.mark.parametrize(
        "idx,name",
        [
            (0, "getOrders"),
            (1, "getUsers"),
            (2, "searchProducts"),
            (3, "updateOrder"),
            (4, "updateUser"),
        ],
    )
    def test_definition_name(self, idx: int, name: str):
        assert TOOL_DEFINITIONS[idx]["function"]["name"] == name

    def test_all_have_type_function(self):
        for td in TOOL_DEFINITIONS:
            assert td["type"] == "function"

    def test_all_have_description(self):
        for td in TOOL_DEFINITIONS:
            assert len(td["function"]["description"]) > 10

    def test_all_have_parameters(self):
        for td in TOOL_DEFINITIONS:
            assert "parameters" in td["function"]
            assert td["function"]["parameters"]["type"] == "object"

    def test_update_order_has_required_fields(self):
        """updateOrder requires order_id and status."""
        td = TOOL_DEFINITIONS[3]
        assert td["function"]["name"] == "updateOrder"
        assert set(td["function"]["parameters"]["required"]) == {"order_id", "status"}

    def test_update_order_status_enum(self):
        """updateOrder status has an enum constraint."""
        td = TOOL_DEFINITIONS[3]
        status_prop = td["function"]["parameters"]["properties"]["status"]
        assert "enum" in status_prop
        assert "shipped" in status_prop["enum"]

    def test_update_user_has_required_user_id(self):
        """updateUser requires user_id."""
        td = TOOL_DEFINITIONS[4]
        assert td["function"]["name"] == "updateUser"
        assert "user_id" in td["function"]["parameters"]["required"]

    def test_definition_names_match_registry(self):
        """Every TOOL_DEFINITION name maps to a TOOL_REGISTRY entry."""
        td_names = {td["function"]["name"] for td in TOOL_DEFINITIONS}
        reg_names = set(TOOL_REGISTRY.keys())
        assert td_names == reg_names


# ═══════════════════════════════════════════════════════════════════════
# 6. System Prompt
# ═══════════════════════════════════════════════════════════════════════


class TestSystemPrompt:
    """SYSTEM_PROMPT for LLM mode."""

    def test_is_non_empty_string(self):
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 50

    def test_mentions_tools(self):
        assert "tool" in SYSTEM_PROMPT.lower()

    def test_mentions_security(self):
        """Prompt instructs LLM to handle security denials."""
        assert "denied" in SYSTEM_PROMPT.lower() or "security" in SYSTEM_PROMPT.lower()


# ═══════════════════════════════════════════════════════════════════════
# 7. __init__.py re-exports
# ═══════════════════════════════════════════════════════════════════════


class TestPackageExports:
    """Verify __init__.py re-exports everything needed."""

    def test_import_execute_tool(self):
        from shared import execute_tool as _et

        assert callable(_et)

    def test_import_tool_registry(self):
        from shared import TOOL_REGISTRY as _tr

        assert len(_tr) == 5

    def test_import_mock_data(self):
        from shared import ORDERS, PRODUCTS, USERS

        assert len(ORDERS) == 5
        assert len(USERS) == 4
        assert len(PRODUCTS) == 6

    def test_import_tool_definitions(self):
        from shared import TOOL_DEFINITIONS as _td

        assert len(_td) == 5

    def test_import_system_prompt(self):
        from shared import SYSTEM_PROMPT as _sp

        assert isinstance(_sp, str)


# ═══════════════════════════════════════════════════════════════════════
# 8. JSON output validity — every tool always produces valid JSON
# ═══════════════════════════════════════════════════════════════════════


class TestAllToolsReturnValidJSON:
    """Every tool function must return a parsable JSON string."""

    @pytest.mark.parametrize(
        "tool_name",
        ["getOrders", "getUsers", "searchProducts", "updateOrder", "updateUser"],
    )
    def test_tool_returns_json_string(self, tool_name: str):
        raw = execute_tool(tool_name)
        assert isinstance(raw, str)
        parsed = json.loads(raw)  # must not raise
        assert isinstance(parsed, dict)

    @pytest.mark.parametrize(
        "tool_name",
        ["getOrders", "getUsers", "searchProducts", "updateOrder", "updateUser"],
    )
    def test_tool_with_none_args(self, tool_name: str):
        raw = execute_tool(tool_name, None)
        json.loads(raw)  # must not raise

    @pytest.mark.parametrize(
        "tool_name",
        ["getOrders", "getUsers", "searchProducts", "updateOrder", "updateUser"],
    )
    def test_tool_with_empty_dict(self, tool_name: str):
        raw = execute_tool(tool_name, {})
        json.loads(raw)  # must not raise
