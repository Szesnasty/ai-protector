"""Tests for LangGraph test agent — Step 04.

Covers:
  - protection.py: SecurityConfig, RBACService, LimitsService, PreToolGate, PostToolGate
  - graph.py: graph compilation, node functions, conditional routing
  - main.py: FastAPI endpoints (/health, /config-status, /chat, /reset-config)
"""

from __future__ import annotations

import json
import os
import sys

import pytest
import pytest_asyncio

# ── path setup so imports work from tests/ ──────────────────────
_agents_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_lg_dir = os.path.join(_agents_root, "langgraph-agent")
for p in (_agents_root, _lg_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

# Module names shared between agents (protection, graph, main).
# When pytest runs multiple test files, the wrong agent's module can
# get cached in sys.modules.  We purge these at fixture time (not
# collection time) so every LG test gets the LangGraph version.
_SHARED_MOD_NAMES = ("protection", "graph", "main")


def _purge_shared_modules() -> None:
    for name in list(sys.modules):
        if name in _SHARED_MOD_NAMES or any(
            name.startswith(f"{m}.") for m in _SHARED_MOD_NAMES
        ):
            del sys.modules[name]
    # Ensure langgraph-agent dir is first in sys.path so the correct
    # protection/graph/main modules are found after the purge.
    if _lg_dir in sys.path:
        sys.path.remove(_lg_dir)
    sys.path.insert(0, _lg_dir)


# ── Fixtures ────────────────────────────────────────────────────

SAMPLE_RBAC = {
    "roles": {
        "user": {
            "tools": {
                "getOrders": {"scopes": ["read"], "sensitivity": "low"},
                "searchProducts": {"scopes": ["read"], "sensitivity": "low"},
            },
        },
        "admin": {
            "inherits": "user",
            "tools": {
                "getUsers": {
                    "scopes": ["read"],
                    "sensitivity": "medium",
                },
                "updateOrder": {
                    "scopes": ["write"],
                    "requires_confirmation": True,
                    "sensitivity": "high",
                },
                "updateUser": {
                    "scopes": ["write"],
                    "requires_confirmation": True,
                    "sensitivity": "high",
                },
            },
        },
    },
}

SAMPLE_LIMITS = {
    "roles": {
        "user": {"max_tool_calls_per_session": 5},
        "admin": {"max_tool_calls_per_session": 50},
    },
}

SAMPLE_POLICY = {
    "policy_pack": "standard",
    "scanners": {
        "pii_redaction": True,
        "injection_detection": True,
    },
}


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset SecurityConfig + graph between tests, purging stale modules."""
    _purge_shared_modules()
    from protection import reset_config
    from graph import reset_graph

    reset_config()
    reset_graph()
    yield
    reset_config()
    reset_graph()


@pytest.fixture()
def loaded_config():
    """Load sample config and return the SecurityConfig."""
    from protection import get_config

    cfg = get_config()
    cfg.load_from_dicts(rbac=SAMPLE_RBAC, limits=SAMPLE_LIMITS, policy=SAMPLE_POLICY)
    return cfg


# =====================================================================
# 1. protection.py unit tests
# =====================================================================


class TestSecurityConfig:
    def test_default_not_loaded(self):
        from protection import get_config

        assert get_config().loaded is False

    def test_load_from_dicts(self, loaded_config):
        assert loaded_config.loaded is True
        assert "user" in loaded_config.rbac["roles"]

    def test_load_from_kit(self):
        import yaml
        from protection import get_config

        kit = {
            "files": {
                "rbac.yaml": yaml.dump(SAMPLE_RBAC),
                "limits.yaml": yaml.dump(SAMPLE_LIMITS),
                "policy.yaml": yaml.dump(SAMPLE_POLICY),
            }
        }
        get_config().load_from_kit(kit)
        assert get_config().loaded is True
        assert "admin" in get_config().rbac["roles"]

    def test_reset_config(self, loaded_config):
        from protection import reset_config, get_config

        reset_config()
        assert get_config().loaded is False
        assert get_config().rbac == {}


class TestRBACService:
    def test_user_can_get_orders(self, loaded_config):
        from protection import RBACService

        result = RBACService().check_permission("user", "getOrders")
        assert result["allowed"] is True
        assert "read" in result["scopes"]

    def test_user_cannot_update_order(self, loaded_config):
        from protection import RBACService

        result = RBACService().check_permission("user", "updateOrder")
        assert result["allowed"] is False

    def test_admin_inherits_user_tools(self, loaded_config):
        from protection import RBACService

        result = RBACService().check_permission("admin", "getOrders")
        assert result["allowed"] is True

    def test_admin_own_tool_requires_confirmation(self, loaded_config):
        from protection import RBACService

        result = RBACService().check_permission("admin", "updateOrder")
        assert result["allowed"] is True
        assert result["requires_confirmation"] is True

    def test_unknown_role(self, loaded_config):
        from protection import RBACService

        result = RBACService().check_permission("guest", "getOrders")
        assert result["allowed"] is False


class TestLimitsService:
    def test_within_limits(self, loaded_config):
        from protection import LimitsService

        svc = LimitsService()
        result = svc.check_limits("user", "getOrders")
        assert result["within_limits"] is True
        assert result["max_calls"] == 5

    def test_exceeds_limits(self, loaded_config):
        from protection import LimitsService

        svc = LimitsService()
        for _ in range(5):
            svc.record_call("user", "getOrders")
        result = svc.check_limits("user", "getOrders")
        assert result["within_limits"] is False

    def test_admin_higher_limits(self, loaded_config):
        from protection import LimitsService

        svc = LimitsService()
        result = svc.check_limits("admin", "getOrders")
        assert result["max_calls"] == 50

    def test_reset(self, loaded_config):
        from protection import LimitsService

        svc = LimitsService()
        svc.record_call("user", "getOrders")
        svc.reset()
        result = svc.check_limits("user", "getOrders")
        assert result["current_calls"] == 0


class TestPreToolGate:
    def test_allow(self, loaded_config):
        from protection import PreToolGate

        result = PreToolGate().check("user", "getOrders")
        assert result["allowed"] is True
        assert result["decision"] == "allow"

    def test_block_rbac(self, loaded_config):
        from protection import PreToolGate

        result = PreToolGate().check("user", "updateOrder")
        assert result["allowed"] is False
        assert result["decision"] == "block"

    def test_confirm(self, loaded_config):
        from protection import PreToolGate

        result = PreToolGate().check("admin", "updateOrder")
        assert result["allowed"] is True
        assert result["decision"] == "confirm"

    def test_block_limits(self, loaded_config):
        from protection import PreToolGate

        gate = PreToolGate()
        for _ in range(5):
            gate.check("user", "getOrders")
        result = gate.check("user", "getOrders")
        assert result["allowed"] is False
        assert "Rate limit" in result["reason"]


class TestPostToolGate:
    def test_clean_output(self, loaded_config):
        from protection import PostToolGate

        result = PostToolGate().scan("Order ORD-001 status: processing")
        assert result["clean"] is True

    def test_detect_email(self, loaded_config):
        from protection import PostToolGate

        result = PostToolGate().scan("User email: alice@example.com")
        assert result["clean"] is False
        assert any(f["subtype"] == "email" for f in result["findings"])

    def test_detect_phone(self, loaded_config):
        from protection import PostToolGate

        result = PostToolGate().scan("Phone: +48 123 456 789")
        assert result["clean"] is False
        assert any(f["subtype"] == "phone" for f in result["findings"])

    def test_detect_injection(self, loaded_config):
        from protection import PostToolGate

        result = PostToolGate().scan("Result: '; -- DROP TABLE users")
        assert result["clean"] is False
        assert any(f["type"] == "injection" for f in result["findings"])

    def test_policy_disabled_pii(self):
        from protection import get_config, PostToolGate

        get_config().load_from_dicts(
            policy={"scanners": {"pii_redaction": False, "injection_detection": True}}
        )
        result = PostToolGate().scan("alice@example.com")
        assert result["clean"] is True

    def test_policy_disabled_injection(self):
        from protection import get_config, PostToolGate

        get_config().load_from_dicts(
            policy={"scanners": {"pii_redaction": True, "injection_detection": False}}
        )
        result = PostToolGate().scan("DROP TABLE users")
        assert result["clean"] is True


# =====================================================================
# 2. graph.py unit tests
# =====================================================================


class TestGraphCompilation:
    def test_graph_compiles(self, loaded_config):
        from graph import build_graph

        g = build_graph()
        compiled = g.compile()
        assert compiled is not None

    def test_get_graph_caches(self, loaded_config):
        from graph import get_graph, reset_graph

        g1 = get_graph()
        g2 = get_graph()
        assert g1 is g2
        reset_graph()
        g3 = get_graph()
        assert g3 is not g1


class TestGraphNodes:
    def test_route_tool_orders(self, loaded_config):
        from graph import route_tool_node

        result = route_tool_node({"message": "show my orders", "role": "user"})
        assert result["tool"] == "getOrders"

    def test_route_tool_update_order(self, loaded_config):
        from graph import route_tool_node

        result = route_tool_node({"message": "update order ORD-001", "role": "admin"})
        assert result["tool"] == "updateOrder"

    def test_route_tool_users(self, loaded_config):
        from graph import route_tool_node

        result = route_tool_node({"message": "list users", "role": "user"})
        assert result["tool"] == "getUsers"

    def test_route_tool_products(self, loaded_config):
        from graph import route_tool_node

        result = route_tool_node({"message": "search for laptop", "role": "user"})
        assert result["tool"] == "searchProducts"

    def test_route_tool_explicit(self, loaded_config):
        from graph import route_tool_node

        result = route_tool_node(
            {"message": "anything", "role": "user", "tool": "getOrders"}
        )
        assert result["tool"] == "getOrders"

    def test_route_tool_none(self, loaded_config):
        from graph import route_tool_node

        result = route_tool_node({"message": "hello world", "role": "user"})
        assert result["tool"] is None

    def test_pre_tool_gate_allow(self, loaded_config):
        from graph import pre_tool_gate_node

        state = {"tool": "getOrders", "role": "user", "gate_log": []}
        result = pre_tool_gate_node(state)
        assert result["pre_gate_result"]["allowed"] is True
        assert len(result["gate_log"]) == 1
        assert result["gate_log"][0]["gate"] == "pre_tool"
        assert result["gate_log"][0]["decision"] == "allow"

    def test_pre_tool_gate_block(self, loaded_config):
        from graph import pre_tool_gate_node

        state = {"tool": "updateOrder", "role": "user", "gate_log": []}
        result = pre_tool_gate_node(state)
        assert result["pre_gate_result"]["allowed"] is False

    def test_pre_tool_gate_no_tool(self, loaded_config):
        from graph import pre_tool_gate_node

        state = {"tool": None, "role": "user", "gate_log": []}
        result = pre_tool_gate_node(state)
        assert result["blocked"] is False
        assert result["no_match"] is True

    def test_tool_executor(self, loaded_config):
        from graph import tool_executor_node

        result = tool_executor_node({"tool": "getOrders", "tool_args": {}})
        assert result["tool_output"] is not None
        parsed = json.loads(result["tool_output"])
        assert "orders" in parsed

    def test_post_tool_gate_clean(self, loaded_config):
        from graph import post_tool_gate_node

        result = post_tool_gate_node({"tool_output": "Order ORD-001", "gate_log": []})
        assert result["post_gate_result"]["clean"] is True
        assert result["gate_log"][0]["decision"] == "clean"

    def test_post_tool_gate_flagged(self, loaded_config):
        from graph import post_tool_gate_node

        result = post_tool_gate_node(
            {"tool_output": "alice@example.com", "gate_log": []}
        )
        assert result["post_gate_result"]["clean"] is False
        assert result["gate_log"][0]["decision"] == "flagged"


class TestConditionalRouting:
    def test_allowed_routes_to_execute(self, loaded_config):
        from graph import after_pre_gate

        state = {"pre_gate_result": {"allowed": True, "requires_confirmation": False}}
        assert after_pre_gate(state) == "execute"

    def test_blocked_routes_to_blocked(self, loaded_config):
        from graph import after_pre_gate

        state = {"pre_gate_result": {"allowed": False}}
        assert after_pre_gate(state) == "blocked"

    def test_confirmation_routes_to_confirm(self, loaded_config):
        from graph import after_pre_gate

        state = {
            "pre_gate_result": {"allowed": True, "requires_confirmation": True},
            "confirmed": False,
        }
        assert after_pre_gate(state) == "confirmation"

    def test_confirmed_routes_to_execute(self, loaded_config):
        from graph import after_pre_gate

        state = {
            "pre_gate_result": {"allowed": True, "requires_confirmation": True},
            "confirmed": True,
        }
        assert after_pre_gate(state) == "execute"

    def test_no_result_routes_to_blocked(self, loaded_config):
        from graph import after_pre_gate

        state = {"pre_gate_result": None}
        assert after_pre_gate(state) == "blocked"

    def test_no_match_routes_to_no_match(self, loaded_config):
        from graph import after_pre_gate

        state = {"no_match": True}
        assert after_pre_gate(state) == "no_match"


class TestFullGraphExecution:
    """End-to-end graph invocation tests."""

    def test_allowed_flow(self, loaded_config):
        from graph import get_graph

        result = get_graph().invoke({"message": "show my orders", "role": "user"})
        assert result.get("blocked") is False
        assert result.get("final_response") is not None
        parsed = json.loads(result["final_response"])
        assert "orders" in parsed
        # gate_log should have pre_tool + post_tool
        gates = [e["gate"] for e in result.get("gate_log", [])]
        assert "pre_tool" in gates
        assert "post_tool" in gates

    def test_blocked_flow(self, loaded_config):
        from graph import get_graph

        result = get_graph().invoke({"message": "update order ORD-001", "role": "user"})
        assert result.get("blocked") is True
        assert "Security" in result.get("final_response", "")

    def test_confirmation_flow(self, loaded_config):
        from graph import get_graph

        result = get_graph().invoke(
            {"message": "update order ORD-001", "role": "admin", "confirmed": False}
        )
        assert result.get("requires_confirmation") is True
        assert "confirmation" in result.get("final_response", "").lower()

    def test_confirmed_flow(self, loaded_config):
        from graph import get_graph

        result = get_graph().invoke(
            {"message": "update order ORD-001", "role": "admin", "confirmed": True}
        )
        assert result.get("blocked") is False
        assert result.get("requires_confirmation") is not True

    def test_pii_flagged_flow(self, loaded_config):
        from graph import get_graph

        result = get_graph().invoke({"message": "list users", "role": "user"})
        post_entries = [
            e for e in result.get("gate_log", []) if e["gate"] == "post_tool"
        ]
        assert len(post_entries) == 1
        assert post_entries[0]["decision"] == "flagged"

    def test_no_tool_flow(self, loaded_config):
        from graph import get_graph

        result = get_graph().invoke({"message": "hello", "role": "user"})
        assert result.get("blocked") is True

    def test_search_products_flow(self, loaded_config):
        from graph import get_graph

        result = get_graph().invoke({"message": "find laptop", "role": "user"})
        assert result.get("blocked") is False
        parsed = json.loads(result["final_response"])
        assert parsed["total"] >= 1


# =====================================================================
# 3. FastAPI endpoint tests
# =====================================================================

import httpx  # noqa: E402


@pytest_asyncio.fixture()
async def client():
    from main import app as fastapi_app
    from protection import reset_config
    from graph import reset_graph

    reset_config()
    reset_graph()
    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    reset_config()
    reset_graph()


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_ok(self, client: httpx.AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["config_loaded"] is False
        assert data["framework"] == "langgraph"


class TestConfigStatusEndpoint:
    @pytest.mark.asyncio
    async def test_no_config(self, client: httpx.AsyncClient):
        resp = await client.get("/config-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["loaded"] is False
        assert data["roles"] == []


class TestResetEndpoint:
    @pytest.mark.asyncio
    async def test_reset(self, client: httpx.AsyncClient):
        from protection import get_config

        get_config().load_from_dicts(rbac=SAMPLE_RBAC)
        resp = await client.post("/reset-config")
        assert resp.status_code == 200
        assert resp.json()["reset"] is True
        assert get_config().loaded is False


class TestChatBeforeConfig:
    @pytest.mark.asyncio
    async def test_chat_without_config_fails(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/chat", json={"message": "show orders", "role": "user"}
        )
        assert resp.status_code == 400


class TestChatEndpoint:
    """Integration tests for POST /chat with loaded config."""

    @pytest_asyncio.fixture(autouse=True)
    async def _load_cfg(self, client):
        from protection import get_config
        from graph import reset_graph

        get_config().load_from_dicts(
            rbac=SAMPLE_RBAC, limits=SAMPLE_LIMITS, policy=SAMPLE_POLICY
        )
        reset_graph()

    @pytest.mark.asyncio
    async def test_show_orders_user(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/chat", json={"message": "show orders", "role": "user"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["blocked"] is False
        assert data["tool"] == "getOrders"
        parsed = json.loads(data["response"])
        assert "orders" in parsed

    @pytest.mark.asyncio
    async def test_update_order_user_blocked(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/chat", json={"message": "update order ORD-001", "role": "user"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["blocked"] is True
        assert "Security" in data["response"]

    @pytest.mark.asyncio
    async def test_update_order_admin_confirmation(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/chat",
            json={
                "message": "update order ORD-001",
                "role": "admin",
                "confirmed": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["requires_confirmation"] is True

    @pytest.mark.asyncio
    async def test_update_order_admin_confirmed(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/chat",
            json={
                "message": "update order ORD-001 shipped",
                "role": "admin",
                "confirmed": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["blocked"] is False
        parsed = json.loads(data["response"])
        assert parsed["success"] is True

    @pytest.mark.asyncio
    async def test_list_users_pii_flagged(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/chat", json={"message": "list users", "role": "user"}
        )
        assert resp.status_code == 200
        data = resp.json()
        post_entries = [e for e in data["gate_log"] if e["gate"] == "post_tool"]
        assert len(post_entries) == 1
        assert post_entries[0]["decision"] == "flagged"
        assert any(f["subtype"] == "email" for f in post_entries[0]["findings"])

    @pytest.mark.asyncio
    async def test_search_products(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/chat", json={"message": "search for laptop", "role": "user"}
        )
        assert resp.status_code == 200
        data = resp.json()
        parsed = json.loads(data["response"])
        assert parsed["total"] >= 1

    @pytest.mark.asyncio
    async def test_gate_log_present(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/chat", json={"message": "show orders", "role": "user"}
        )
        data = resp.json()
        assert "gate_log" in data
        assert len(data["gate_log"]) >= 1

    @pytest.mark.asyncio
    async def test_graph_nodes_visited(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/chat", json={"message": "show orders", "role": "user"}
        )
        data = resp.json()
        assert "graph_nodes_visited" in data
        assert "pre_tool" in data["graph_nodes_visited"]
        assert "post_tool" in data["graph_nodes_visited"]

    @pytest.mark.asyncio
    async def test_explicit_tool(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/chat",
            json={"message": "anything", "role": "user", "tool": "getOrders"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tool"] == "getOrders"
        assert data["blocked"] is False

    @pytest.mark.asyncio
    async def test_no_tool_matched(self, client: httpx.AsyncClient):
        resp = await client.post("/chat", json={"message": "hello", "role": "user"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["blocked"] is False
        assert data["no_match"] is True
