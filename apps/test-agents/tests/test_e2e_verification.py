"""
Step 07 — End-to-End Verification for Agent Wizard Go-Live.

Full flow: create agent via wizard API → register tools → create roles
→ set permissions → generate integration kit → load into test agent
→ chat with security enforcement → verify all gate decisions.

Runs for both Pure Python (port 8003) and LangGraph (port 8004).

Usage:
    python apps/test-agents/tests/test_e2e_verification.py
    # Or via pytest:
    cd apps/proxy-service && .venv/bin/python -m pytest ../test-agents/tests/test_e2e_verification.py -v

Requires: proxy-service (:8000), test-agent-python (:8003), test-agent-langgraph (:8004) running.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass

import httpx

PROXY = "http://localhost:8000"
PYTHON_AGENT = "http://localhost:8003"
GRAPH_AGENT = "http://localhost:8004"


@dataclass
class AgentSetup:
    """Holds IDs from wizard setup."""

    agent_id: str
    tool_ids: dict[str, str]  # name → id
    role_ids: dict[str, str]  # name → id


# ──────────────────────────────────────────────────────────────────────
# Wizard API Helpers
# ──────────────────────────────────────────────────────────────────────


def create_agent(client: httpx.Client, name: str, framework: str) -> str:
    """Create a wizard agent, return its ID."""
    resp = client.post(
        f"{PROXY}/v1/agents",
        json={
            "name": name,
            "description": "E2E test agent",
            "framework": framework,
            "environment": "dev",
            "team": "QA",
            "has_tools": True,
            "has_write_actions": True,
            "touches_pii": True,
        },
    )
    if resp.status_code == 409:
        # Agent already exists — find it
        list_resp = client.get(f"{PROXY}/v1/agents")
        for a in list_resp.json()["items"]:
            if a["name"] == name:
                return a["id"]
    assert resp.status_code == 201, (
        f"create_agent failed: {resp.status_code} {resp.text}"
    )
    return resp.json()["id"]


TOOLS = [
    {
        "name": "getOrders",
        "description": "List all orders",
        "access_type": "read",
        "sensitivity": "low",
        "returns_pii": False,
    },
    {
        "name": "getUsers",
        "description": "List all users",
        "access_type": "read",
        "sensitivity": "medium",
        "returns_pii": True,
    },
    {
        "name": "searchProducts",
        "description": "Search product catalog",
        "access_type": "read",
        "sensitivity": "low",
        "returns_pii": False,
    },
    {
        "name": "updateOrder",
        "description": "Update order status",
        "access_type": "write",
        "sensitivity": "high",
        "returns_pii": False,
    },
    {
        "name": "updateUser",
        "description": "Update user profile",
        "access_type": "write",
        "sensitivity": "high",
        "returns_pii": False,
    },
]


def register_tools(client: httpx.Client, agent_id: str) -> dict[str, str]:
    """Register 5 tools, return name→id mapping."""
    tool_ids: dict[str, str] = {}
    for t in TOOLS:
        resp = client.post(f"{PROXY}/v1/agents/{agent_id}/tools", json=t)
        if resp.status_code == 409:
            # Already exists — list and find
            list_resp = client.get(f"{PROXY}/v1/agents/{agent_id}/tools")
            for existing in list_resp.json():
                if existing["name"] == t["name"]:
                    tool_ids[t["name"]] = existing["id"]
                    break
        else:
            assert resp.status_code == 201, (
                f"create tool {t['name']} failed: {resp.status_code} {resp.text}"
            )
            tool_ids[t["name"]] = resp.json()["id"]
    return tool_ids


def create_roles_and_permissions(
    client: httpx.Client, agent_id: str, tool_ids: dict[str, str]
) -> dict[str, str]:
    """Create user + admin roles with permissions, return name→id mapping."""
    role_ids: dict[str, str] = {}

    # Create 'user' role
    resp = client.post(
        f"{PROXY}/v1/agents/{agent_id}/roles",
        json={"name": "user", "description": "Standard user"},
    )
    if resp.status_code == 409:
        list_resp = client.get(f"{PROXY}/v1/agents/{agent_id}/roles")
        for r in list_resp.json():
            if r["name"] == "user":
                role_ids["user"] = r["id"]
    else:
        assert resp.status_code == 201, (
            f"create role 'user' failed: {resp.status_code} {resp.text}"
        )
        role_ids["user"] = resp.json()["id"]

    # Create 'admin' role (inherits from user)
    resp = client.post(
        f"{PROXY}/v1/agents/{agent_id}/roles",
        json={
            "name": "admin",
            "description": "Admin user",
            "inherits_from": role_ids["user"],
        },
    )
    if resp.status_code == 409:
        list_resp = client.get(f"{PROXY}/v1/agents/{agent_id}/roles")
        for r in list_resp.json():
            if r["name"] == "admin":
                role_ids["admin"] = r["id"]
    else:
        assert resp.status_code == 201, (
            f"create role 'admin' failed: {resp.status_code} {resp.text}"
        )
        role_ids["admin"] = resp.json()["id"]

    # Set user permissions: getOrders, getUsers, searchProducts — read only
    user_perms = [
        {"tool_id": tool_ids["getOrders"], "scopes": ["read"]},
        {"tool_id": tool_ids["getUsers"], "scopes": ["read"]},
        {"tool_id": tool_ids["searchProducts"], "scopes": ["read"]},
    ]
    resp = client.put(
        f"{PROXY}/v1/agents/{agent_id}/roles/{role_ids['user']}/permissions",
        json={"permissions": user_perms},
    )
    assert resp.status_code == 200, (
        f"set user perms failed: {resp.status_code} {resp.text}"
    )

    # Set admin permissions: updateOrder, updateUser — read+write with confirmation
    admin_perms = [
        {
            "tool_id": tool_ids["updateOrder"],
            "scopes": ["read", "write"],
            "requires_confirmation_override": True,
        },
        {
            "tool_id": tool_ids["updateUser"],
            "scopes": ["read", "write"],
            "requires_confirmation_override": True,
        },
    ]
    resp = client.put(
        f"{PROXY}/v1/agents/{agent_id}/roles/{role_ids['admin']}/permissions",
        json={"permissions": admin_perms},
    )
    assert resp.status_code == 200, (
        f"set admin perms failed: {resp.status_code} {resp.text}"
    )

    return role_ids


def generate_kit(client: httpx.Client, agent_id: str) -> dict:
    """Generate integration kit via wizard API."""
    # First generate configs
    resp = client.post(f"{PROXY}/v1/agents/{agent_id}/generate-config")
    assert resp.status_code == 200, (
        f"generate config failed: {resp.status_code} {resp.text}"
    )

    # Then generate kit
    resp = client.post(f"{PROXY}/v1/agents/{agent_id}/integration-kit")
    assert resp.status_code == 200, (
        f"generate kit failed: {resp.status_code} {resp.text}"
    )
    kit = resp.json()
    assert "files" in kit, f"Kit missing 'files' key: {list(kit.keys())}"
    return kit


def setup_wizard_agent(client: httpx.Client, name: str, framework: str) -> AgentSetup:
    """Full wizard setup: create agent → tools → roles → permissions → generate kit."""
    agent_id = create_agent(client, name, framework)
    print(f"  ✅ Agent created: {name} ({agent_id[:8]}...)")

    tool_ids = register_tools(client, agent_id)
    print(f"  ✅ {len(tool_ids)} tools registered")

    role_ids = create_roles_and_permissions(client, agent_id, tool_ids)
    print(f"  ✅ Roles created: {list(role_ids.keys())}")

    kit = generate_kit(client, agent_id)
    print(f"  ✅ Integration kit generated: {list(kit.get('files', {}).keys())}")

    return AgentSetup(agent_id=agent_id, tool_ids=tool_ids, role_ids=role_ids)


# ──────────────────────────────────────────────────────────────────────
# Test Agent Interaction Helpers
# ──────────────────────────────────────────────────────────────────────


def load_config(client: httpx.Client, agent_url: str, agent_id: str) -> dict:
    """Load wizard config into test agent."""
    resp = client.post(f"{agent_url}/load-config", json={"agent_id": agent_id})
    assert resp.status_code == 200, (
        f"load-config failed: {resp.status_code} {resp.text}"
    )
    data = resp.json()
    assert data.get("loaded"), "Config not loaded"
    return data


def chat(
    client: httpx.Client,
    agent_url: str,
    message: str,
    role: str,
    confirmed: bool = False,
    tool: str | None = None,
    tool_args: dict | None = None,
) -> dict:
    """Send a chat message to test agent."""
    body: dict = {
        "message": message,
        "role": role,
        "mode": "mock",
        "confirmed": confirmed,
    }
    if tool:
        body["tool"] = tool
    if tool_args:
        body["tool_args"] = tool_args
    resp = client.post(f"{agent_url}/chat", json=body)
    assert resp.status_code == 200, f"chat failed: {resp.status_code} {resp.text}"
    return resp.json()


def chat_expect_error(
    client: httpx.Client, agent_url: str, message: str, role: str = "user"
) -> dict:
    """Send a chat message that we expect to fail (non-200)."""
    resp = client.post(
        f"{agent_url}/chat", json={"message": message, "role": role, "mode": "mock"}
    )
    return {"status_code": resp.status_code, "detail": resp.text}


# ──────────────────────────────────────────────────────────────────────
# E2E Test Cases
# ──────────────────────────────────────────────────────────────────────


def run_test_cases(
    client: httpx.Client, agent_url: str, framework_label: str, setup: AgentSetup
) -> tuple[int, int]:
    """Run the 10 test cases from the spec. Returns (passed, failed)."""
    passed = 0
    failed = 0

    def check(name: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"    ✅ {name}")
        else:
            failed += 1
            print(f"    ❌ {name}: {detail}")

    # Load config
    cfg = load_config(client, agent_url, setup.agent_id)
    check("Load config", cfg.get("loaded", False))

    # Get config status
    status_resp = client.get(f"{agent_url}/config-status")
    status = status_resp.json()
    check(
        "Config status has roles",
        len(status.get("roles", [])) >= 2,
        f"roles={status.get('roles')}",
    )

    print("\n  --- Test cases as 'user' ---")

    # Test 1: getOrders (user) → ALLOW
    r = chat(client, agent_url, "show me all orders", "user")
    check(
        "T1: getOrders (user) → allowed",
        not r.get("blocked", True),
        f"blocked={r.get('blocked')}",
    )
    gate_log = r.get("gate_log", [])
    has_allow = any(e.get("decision", "").upper() == "ALLOW" for e in gate_log)
    check("T1: gate_log has ALLOW", has_allow, f"gate_log={json.dumps(gate_log)[:200]}")

    # Test 2: getUsers (user) → ALLOW + PII flagged
    r = chat(client, agent_url, "list all users", "user")
    check("T2: getUsers (user) → allowed", not r.get("blocked", True))
    gate_log = r.get("gate_log", [])
    has_pii = any(
        e.get("decision", "").upper() == "FLAGGED"
        or any(
            f.get("type", "").lower() in ("pii", "email", "phone")
            for f in (e.get("findings") or e.get("scan_findings") or [])
        )
        for e in gate_log
    )
    check(
        "T2: PII flagged in gate_log", has_pii, f"gate_log={json.dumps(gate_log)[:300]}"
    )

    # Test 3: searchProducts (user) → ALLOW
    r = chat(client, agent_url, "search products laptop", "user")
    check("T3: searchProducts (user) → allowed", not r.get("blocked", True))

    # Test 4: updateOrder (user) → BLOCKED
    r = chat(client, agent_url, "update order ORD-001 to shipped", "user")
    check("T4: updateOrder (user) → blocked", r.get("blocked", False))
    gate_log = r.get("gate_log", [])
    has_block = any(
        e.get("decision", "").upper() in ("BLOCK", "DENY") for e in gate_log
    )
    check("T4: gate_log has BLOCK", has_block, f"gate_log={json.dumps(gate_log)[:200]}")

    # Test 5: updateUser (user) → BLOCKED
    r = chat(client, agent_url, "update user USR-002", "user")
    check("T5: updateUser (user) → blocked", r.get("blocked", False))

    print("\n  --- Test cases as 'admin' ---")

    # Test 6: getOrders (admin) → ALLOW (inherited)
    r = chat(client, agent_url, "show me all orders", "admin")
    check("T6: getOrders (admin) → allowed", not r.get("blocked", True))

    # Test 7: updateOrder (admin) → CONFIRM
    r = chat(client, agent_url, "update order ORD-001 to shipped", "admin")
    check(
        "T7: updateOrder (admin) → requires confirmation",
        r.get("requires_confirmation", False),
        f"response={json.dumps(r)[:300]}",
    )

    # Test 8: Confirm updateOrder
    r2 = chat(
        client,
        agent_url,
        "update order ORD-001 to shipped",
        "admin",
        confirmed=True,
        tool=r.get("tool"),
        tool_args=r.get("tool_args"),
    )
    check("T8: confirmed updateOrder → not blocked", not r2.get("blocked", True))

    # Test 9: updateUser (admin) → CONFIRM
    r = chat(client, agent_url, "update user USR-001", "admin")
    check(
        "T9: updateUser (admin) → requires confirmation",
        r.get("requires_confirmation", False),
    )

    # Test 10: Confirm updateUser
    r2 = chat(
        client,
        agent_url,
        "update user USR-001",
        "admin",
        confirmed=True,
        tool=r.get("tool"),
        tool_args=r.get("tool_args"),
    )
    check("T10: confirmed updateUser → not blocked", not r2.get("blocked", True))

    return passed, failed


def run_regression_cases(
    client: httpx.Client, agent_url: str, setup: AgentSetup
) -> tuple[int, int]:
    """Run the 8 regression edge cases."""
    passed = 0
    failed = 0

    def check(name: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"    ✅ {name}")
        else:
            failed += 1
            print(f"    ❌ {name}: {detail}")

    print("\n  --- Regression edge cases ---")

    # R1: Chat without config → reset first
    client.post(f"{agent_url}/reset-config")
    resp = client.post(
        f"{agent_url}/chat", json={"message": "hello", "role": "user", "mode": "mock"}
    )
    check(
        "R1: Chat without config → error",
        resp.status_code == 400,
        f"status={resp.status_code}",
    )

    # Reload config for remaining tests
    load_config(client, agent_url, setup.agent_id)

    # R2: Load config with invalid agent ID → error
    resp = client.post(
        f"{agent_url}/load-config",
        json={"agent_id": "00000000-0000-0000-0000-000000000000"},
    )
    check(
        "R2: Invalid agent ID → error",
        resp.status_code in (400, 404, 502),
        f"status={resp.status_code}",
    )

    # Re-load valid config
    load_config(client, agent_url, setup.agent_id)

    # R3: Empty message
    r = chat(client, agent_url, "", "user")
    check(
        "R3: Empty message → no crash",
        "response" in r,
        f"response keys: {list(r.keys())}",
    )

    # R4: Unknown tool name
    r = chat(client, agent_url, "do something weird", "user")
    check("R4: Unknown tool → not blocked crash", "response" in r)

    # R5: Switch agent → re-load clears old config
    client.post(f"{agent_url}/reset-config")
    load_config(client, agent_url, setup.agent_id)
    status = client.get(f"{agent_url}/config-status").json()
    check("R5: Re-load config → roles present", len(status.get("roles", [])) >= 2)

    # R6: Admin confirm write → post-gate scan runs
    r = chat(client, agent_url, "update order ORD-001 to shipped", "admin")
    if r.get("requires_confirmation"):
        r2 = chat(
            client,
            agent_url,
            "update order ORD-001 to shipped",
            "admin",
            confirmed=True,
            tool=r.get("tool"),
            tool_args=r.get("tool_args"),
        )
        gate_log = r2.get("gate_log", [])
        has_post = any("post" in e.get("gate", "").lower() for e in gate_log)
        check(
            "R6: Confirmed write → post-gate scan runs",
            has_post,
            f"gate_log={json.dumps(gate_log)[:200]}",
        )
    else:
        check(
            "R6: Confirmed write → post-gate scan runs",
            False,
            "No confirmation was required",
        )

    # R7: PII in getUsers
    r = chat(client, agent_url, "list all users", "user")
    gate_log = r.get("gate_log", [])
    has_pii = any(
        len(e.get("findings") or e.get("scan_findings") or []) > 0 for e in gate_log
    )
    check(
        "R7: PII in getUsers detected",
        has_pii,
        f"gate_log={json.dumps(gate_log)[:200]}",
    )

    # R8: Re-generate kit → reload
    resp = client.post(f"{PROXY}/v1/agents/{setup.agent_id}/integration-kit")
    assert resp.status_code == 200
    load_config(client, agent_url, setup.agent_id)
    r = chat(client, agent_url, "show me all orders", "user")
    check("R8: Re-generated kit + reload → still works", not r.get("blocked", True))

    return passed, failed


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────


def preflight() -> bool:
    """Check all services are reachable."""
    services = {
        "proxy-service": f"{PROXY}/health",
        "test-agent-python": f"{PYTHON_AGENT}/health",
        "test-agent-langgraph": f"{GRAPH_AGENT}/health",
    }
    all_ok = True
    for name, url in services.items():
        try:
            r = httpx.get(url, timeout=5)
            if r.status_code == 200:
                print(f"  ✅ {name}: OK")
            else:
                print(f"  ❌ {name}: HTTP {r.status_code}")
                all_ok = False
        except httpx.ConnectError:
            print(f"  ❌ {name}: not reachable")
            all_ok = False
    return all_ok


def cleanup_agent(client: httpx.Client, name: str):
    """Try to delete agent by name (best-effort cleanup)."""
    try:
        resp = client.get(f"{PROXY}/v1/agents")
        for a in resp.json().get("items", []):
            if a["name"] == name:
                client.delete(f"{PROXY}/v1/agents/{a['id']}")
    except Exception:
        pass


def main():
    print("\n" + "=" * 60)
    print("  Step 07 — End-to-End Verification")
    print("=" * 60)

    print("\n🔍 Pre-flight check...")
    if not preflight():
        print("\n❌ Not all services are running. Aborting.")
        sys.exit(1)

    total_passed = 0
    total_failed = 0

    with httpx.Client(timeout=30) as client:
        # ── Scenario A: Pure Python Agent ────────────────────────
        print("\n" + "-" * 60)
        print("  Scenario A: Pure Python Agent")
        print("-" * 60)

        agent_name_py = f"E2E-Python-{int(time.time())}"
        print(f"\n  Setting up wizard agent: {agent_name_py}")
        setup_py = setup_wizard_agent(client, agent_name_py, "raw_python")

        print(f"\n  Running test cases against {PYTHON_AGENT}...")
        p, f = run_test_cases(client, PYTHON_AGENT, "Pure Python", setup_py)
        total_passed += p
        total_failed += f

        p, f = run_regression_cases(client, PYTHON_AGENT, setup_py)
        total_passed += p
        total_failed += f

        # ── Scenario B: LangGraph Agent ─────────────────────────
        print("\n" + "-" * 60)
        print("  Scenario B: LangGraph Agent")
        print("-" * 60)

        agent_name_lg = f"E2E-LangGraph-{int(time.time())}"
        print(f"\n  Setting up wizard agent: {agent_name_lg}")
        setup_lg = setup_wizard_agent(client, agent_name_lg, "langgraph")

        print(f"\n  Running test cases against {GRAPH_AGENT}...")
        p, f = run_test_cases(client, GRAPH_AGENT, "LangGraph", setup_lg)
        total_passed += p
        total_failed += f

        p, f = run_regression_cases(client, GRAPH_AGENT, setup_lg)
        total_passed += p
        total_failed += f

        # ── Cleanup ─────────────────────────────────────────────
        print("\n  Cleaning up test agents...")
        cleanup_agent(client, agent_name_py)
        cleanup_agent(client, agent_name_lg)

    # ── Summary ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  RESULTS: {total_passed} passed, {total_failed} failed")
    print("=" * 60)

    if total_failed > 0:
        print("\n❌ Some tests FAILED")
        sys.exit(1)
    else:
        print("\n✅ All tests PASSED — Agent Wizard Go-Live verified!")
        sys.exit(0)


if __name__ == "__main__":
    main()
