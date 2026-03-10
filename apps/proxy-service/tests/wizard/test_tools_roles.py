"""Tests for Tools & Roles CRUD — spec 27 (52 tests).

Covers:
  27a — Tool CRUD + smart defaults (18 tests)
  27b — Role CRUD + inheritance (20 tests)
  27c — Permission matrix (8 tests)
  27d — Seed (6 tests)
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.wizard.seed import (
    REFERENCE_AGENT,
    seed_reference_agent,
    seed_reference_tools_and_roles,
)


@pytest.fixture
async def client():
    """Async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Helpers ──────────────────────────────────────────────────────────────

_AGENT_BODY = {
    "name": f"ToolRoleTestAgent-{uuid.uuid4().hex[:8]}",
    "description": "Agent for tool/role tests",
    "team": "platform",
    "framework": "langgraph",
    "environment": "dev",
    "is_public_facing": False,
    "has_tools": True,
    "has_write_actions": False,
    "touches_pii": False,
    "handles_secrets": False,
    "calls_external_apis": False,
}

_TOOL_BODY = {
    "name": "testTool",
    "description": "A test tool",
    "category": "testing",
    "access_type": "read",
    "sensitivity": "low",
}


async def _create_agent(client: AsyncClient, name_suffix: str = "") -> dict:
    body = {**_AGENT_BODY, "name": f"ToolRoleAgent-{uuid.uuid4().hex[:8]}{name_suffix}"}
    resp = await client.post("/v1/agents", json=body)
    assert resp.status_code == 201
    return resp.json()


async def _create_tool(client: AsyncClient, agent_id: str, **overrides) -> dict:
    body = {**_TOOL_BODY, "name": f"tool-{uuid.uuid4().hex[:8]}", **overrides}
    resp = await client.post(f"/v1/agents/{agent_id}/tools", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_role(client: AsyncClient, agent_id: str, **overrides) -> dict:
    body = {"name": f"role-{uuid.uuid4().hex[:8]}", "description": "test role", **overrides}
    resp = await client.post(f"/v1/agents/{agent_id}/roles", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ═══════════════════════════════════════════════════════════════════════
# 27a — Tool CRUD (18 tests)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_tool(client):
    """POST → 201, tool has id + agent_id."""
    agent = await _create_agent(client)
    tool = await _create_tool(client, agent["id"])
    assert "id" in tool
    assert tool["agent_id"] == agent["id"]


@pytest.mark.asyncio
async def test_create_tool_missing_name(client):
    """POST without name → 422."""
    agent = await _create_agent(client)
    resp = await client.post(f"/v1/agents/{agent['id']}/tools", json={"description": "no name"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_tool_duplicate_name(client):
    """Same tool name on same agent → 409."""
    agent = await _create_agent(client)
    name = f"dup-{uuid.uuid4().hex[:8]}"
    await _create_tool(client, agent["id"], name=name)
    resp = await client.post(
        f"/v1/agents/{agent['id']}/tools",
        json={**_TOOL_BODY, "name": name},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_tool_same_name_diff_agent(client):
    """Same tool name on different agent → 201 (allowed)."""
    a1 = await _create_agent(client, "-A")
    a2 = await _create_agent(client, "-B")
    name = f"shared-{uuid.uuid4().hex[:8]}"
    await _create_tool(client, a1["id"], name=name)
    resp = await client.post(
        f"/v1/agents/{a2['id']}/tools",
        json={**_TOOL_BODY, "name": name},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_tool_smart_default_confirmation(client):
    """write + high → requires_confirmation=true auto-set."""
    agent = await _create_agent(client)
    tool = await _create_tool(client, agent["id"], access_type="write", sensitivity="high")
    assert tool["requires_confirmation"] is True


@pytest.mark.asyncio
async def test_create_tool_smart_default_no_confirmation(client):
    """read + low → requires_confirmation=false."""
    agent = await _create_agent(client)
    tool = await _create_tool(client, agent["id"], access_type="read", sensitivity="low")
    assert tool["requires_confirmation"] is False


@pytest.mark.asyncio
async def test_create_tool_smart_default_rate_limit_low(client):
    """sensitivity=low → rate_limit defaults to 20."""
    agent = await _create_agent(client)
    tool = await _create_tool(client, agent["id"], sensitivity="low")
    assert tool["rate_limit"] == 20


@pytest.mark.asyncio
async def test_create_tool_smart_default_rate_limit_critical(client):
    """sensitivity=critical → rate_limit defaults to 3."""
    agent = await _create_agent(client)
    tool = await _create_tool(client, agent["id"], sensitivity="critical")
    assert tool["rate_limit"] == 3


@pytest.mark.asyncio
async def test_create_tool_with_arg_schema(client):
    """Valid JSON Schema in arg_schema → accepted."""
    agent = await _create_agent(client)
    schema = {"type": "object", "properties": {"query": {"type": "string"}}}
    tool = await _create_tool(client, agent["id"], arg_schema=schema)
    assert tool["arg_schema"] == schema


@pytest.mark.asyncio
async def test_create_tool_invalid_arg_schema(client):
    """Non-dict arg_schema → 422."""
    agent = await _create_agent(client)
    resp = await client.post(
        f"/v1/agents/{agent['id']}/tools",
        json={**_TOOL_BODY, "name": f"bad-{uuid.uuid4().hex[:8]}", "arg_schema": "not-a-dict"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_tools_empty(client):
    """GET /agents/:id/tools on new agent → []."""
    agent = await _create_agent(client)
    resp = await client.get(f"/v1/agents/{agent['id']}/tools")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_tools_returns_all(client):
    """Create 5 tools, GET → 5 items."""
    agent = await _create_agent(client)
    for _i in range(5):
        await _create_tool(client, agent["id"])
    resp = await client.get(f"/v1/agents/{agent['id']}/tools")
    assert len(resp.json()) == 5


@pytest.mark.asyncio
async def test_list_tools_scoped_to_agent(client):
    """Tools from agent A not visible in agent B."""
    a1 = await _create_agent(client)
    a2 = await _create_agent(client)
    await _create_tool(client, a1["id"])
    resp = await client.get(f"/v1/agents/{a2['id']}/tools")
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_patch_tool(client):
    """PATCH name → updated."""
    agent = await _create_agent(client)
    tool = await _create_tool(client, agent["id"])
    new_name = f"patched-{uuid.uuid4().hex[:8]}"
    resp = await client.patch(
        f"/v1/agents/{agent['id']}/tools/{tool['id']}",
        json={"name": new_name},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == new_name


@pytest.mark.asyncio
async def test_patch_tool_recomputes_confirmation(client):
    """PATCH sensitivity=critical on write tool → requires_confirmation flips to true."""
    agent = await _create_agent(client)
    tool = await _create_tool(client, agent["id"], access_type="write", sensitivity="low")
    assert tool["requires_confirmation"] is False

    resp = await client.patch(
        f"/v1/agents/{agent['id']}/tools/{tool['id']}",
        json={"sensitivity": "critical"},
    )
    assert resp.status_code == 200
    assert resp.json()["requires_confirmation"] is True


@pytest.mark.asyncio
async def test_delete_tool(client):
    """DELETE → 204, not in list anymore."""
    agent = await _create_agent(client)
    tool = await _create_tool(client, agent["id"])
    resp = await client.delete(f"/v1/agents/{agent['id']}/tools/{tool['id']}")
    assert resp.status_code == 204
    # Verify gone
    resp = await client.get(f"/v1/agents/{agent['id']}/tools")
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_delete_tool_not_found(client):
    """DELETE nonexistent → 404."""
    agent = await _create_agent(client)
    resp = await client.delete(f"/v1/agents/{agent['id']}/tools/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_tool_cascades_permissions(client):
    """Delete tool → role_tool_permissions for this tool also gone."""
    agent = await _create_agent(client)
    tool = await _create_tool(client, agent["id"])
    role = await _create_role(client, agent["id"])

    # Set permission
    await client.put(
        f"/v1/agents/{agent['id']}/roles/{role['id']}/permissions",
        json={"permissions": [{"tool_id": tool["id"], "scopes": ["read"]}]},
    )

    # Delete the tool
    resp = await client.delete(f"/v1/agents/{agent['id']}/tools/{tool['id']}")
    assert resp.status_code == 204

    # Verify permissions cleared (role should have no permissions)
    resp = await client.get(f"/v1/agents/{agent['id']}/roles")
    roles = resp.json()
    target_role = next(r for r in roles if r["id"] == role["id"])
    assert len(target_role["permissions"]) == 0


# ═══════════════════════════════════════════════════════════════════════
# 27b — Role CRUD + Inheritance (20 tests)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_role(client):
    """POST → 201, role has id + agent_id."""
    agent = await _create_agent(client)
    role = await _create_role(client, agent["id"])
    assert "id" in role
    assert role["agent_id"] == agent["id"]


@pytest.mark.asyncio
async def test_create_role_missing_name(client):
    """POST without name → 422."""
    agent = await _create_agent(client)
    resp = await client.post(f"/v1/agents/{agent['id']}/roles", json={"description": "no name"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_role_duplicate_name(client):
    """Same role name on same agent → 409."""
    agent = await _create_agent(client)
    name = f"dup-role-{uuid.uuid4().hex[:8]}"
    await _create_role(client, agent["id"], name=name)
    resp = await client.post(
        f"/v1/agents/{agent['id']}/roles",
        json={"name": name, "description": "dup"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_role_with_inheritance(client):
    """POST inherits_from=parent_id → 201."""
    agent = await _create_agent(client)
    parent = await _create_role(client, agent["id"], name=f"parent-{uuid.uuid4().hex[:8]}")
    child = await _create_role(
        client,
        agent["id"],
        name=f"child-{uuid.uuid4().hex[:8]}",
        inherits_from=parent["id"],
    )
    assert child["inherits_from"] == parent["id"]


@pytest.mark.asyncio
async def test_create_role_circular_inheritance(client):
    """Role A inherits B, update B to inherit A → 422."""
    agent = await _create_agent(client)
    a = await _create_role(client, agent["id"], name=f"a-{uuid.uuid4().hex[:8]}")
    b = await _create_role(
        client,
        agent["id"],
        name=f"b-{uuid.uuid4().hex[:8]}",
        inherits_from=a["id"],
    )
    # Now try to make A inherit B → cycle
    resp = await client.patch(
        f"/v1/agents/{agent['id']}/roles/{a['id']}",
        json={"inherits_from": b["id"]},
    )
    assert resp.status_code == 422
    assert "circular" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_role_deep_circular(client):
    """A→B→C, update C to inherit A → 422."""
    agent = await _create_agent(client)
    a = await _create_role(client, agent["id"], name=f"da-{uuid.uuid4().hex[:8]}")
    b = await _create_role(client, agent["id"], name=f"db-{uuid.uuid4().hex[:8]}", inherits_from=a["id"])
    c = await _create_role(client, agent["id"], name=f"dc-{uuid.uuid4().hex[:8]}", inherits_from=b["id"])
    # Try C → A; but actually we want A → C (since C→B→A, making A inherit C creates A→C→B→A cycle)
    resp = await client.patch(
        f"/v1/agents/{agent['id']}/roles/{a['id']}",
        json={"inherits_from": c["id"]},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_roles(client):
    """GET → all roles with resolved permissions."""
    agent = await _create_agent(client)
    await _create_role(client, agent["id"])
    await _create_role(client, agent["id"])
    resp = await client.get(f"/v1/agents/{agent['id']}/roles")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_roles_scoped_to_agent(client):
    """Roles from agent A not in agent B."""
    a1 = await _create_agent(client)
    a2 = await _create_agent(client)
    await _create_role(client, a1["id"])
    resp = await client.get(f"/v1/agents/{a2['id']}/roles")
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_patch_role(client):
    """PATCH name → updated."""
    agent = await _create_agent(client)
    role = await _create_role(client, agent["id"])
    new_name = f"patched-{uuid.uuid4().hex[:8]}"
    resp = await client.patch(
        f"/v1/agents/{agent['id']}/roles/{role['id']}",
        json={"name": new_name},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == new_name


@pytest.mark.asyncio
async def test_delete_role(client):
    """DELETE → 204, cascade permissions deleted."""
    agent = await _create_agent(client)
    role = await _create_role(client, agent["id"])
    tool = await _create_tool(client, agent["id"])

    # Set a permission
    await client.put(
        f"/v1/agents/{agent['id']}/roles/{role['id']}/permissions",
        json={"permissions": [{"tool_id": tool["id"]}]},
    )

    resp = await client.delete(f"/v1/agents/{agent['id']}/roles/{role['id']}")
    assert resp.status_code == 204

    # Role gone
    resp = await client.get(f"/v1/agents/{agent['id']}/roles")
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_delete_role_with_children(client):
    """DELETE parent role → children's inherits_from set to null."""
    agent = await _create_agent(client)
    parent = await _create_role(client, agent["id"], name=f"parent-{uuid.uuid4().hex[:8]}")
    child = await _create_role(
        client,
        agent["id"],
        name=f"child-{uuid.uuid4().hex[:8]}",
        inherits_from=parent["id"],
    )

    resp = await client.delete(f"/v1/agents/{agent['id']}/roles/{parent['id']}")
    assert resp.status_code == 204

    # Child's inherits_from should now be null
    resp = await client.get(f"/v1/agents/{agent['id']}/roles")
    roles = resp.json()
    child_role = next(r for r in roles if r["id"] == child["id"])
    assert child_role["inherits_from"] is None


@pytest.mark.asyncio
async def test_set_permissions_batch(client):
    """PUT permissions → all tool->role links created."""
    agent = await _create_agent(client)
    t1 = await _create_tool(client, agent["id"])
    t2 = await _create_tool(client, agent["id"])
    role = await _create_role(client, agent["id"])

    resp = await client.put(
        f"/v1/agents/{agent['id']}/roles/{role['id']}/permissions",
        json={
            "permissions": [
                {"tool_id": t1["id"], "scopes": ["read"]},
                {"tool_id": t2["id"], "scopes": ["read", "write"]},
            ]
        },
    )
    assert resp.status_code == 200
    perms = resp.json()
    assert len(perms) == 2


@pytest.mark.asyncio
async def test_set_permissions_overwrites(client):
    """PUT twice → second call replaces first."""
    agent = await _create_agent(client)
    t1 = await _create_tool(client, agent["id"])
    t2 = await _create_tool(client, agent["id"])
    role = await _create_role(client, agent["id"])

    # First set: t1
    await client.put(
        f"/v1/agents/{agent['id']}/roles/{role['id']}/permissions",
        json={"permissions": [{"tool_id": t1["id"]}]},
    )

    # Second set: t2 only
    resp = await client.put(
        f"/v1/agents/{agent['id']}/roles/{role['id']}/permissions",
        json={"permissions": [{"tool_id": t2["id"]}]},
    )
    assert resp.status_code == 200
    perms = resp.json()
    assert len(perms) == 1
    assert perms[0]["tool_id"] == t2["id"]


@pytest.mark.asyncio
async def test_set_permissions_invalid_tool(client):
    """Permission for nonexistent tool → 422."""
    agent = await _create_agent(client)
    role = await _create_role(client, agent["id"])
    resp = await client.put(
        f"/v1/agents/{agent['id']}/roles/{role['id']}/permissions",
        json={"permissions": [{"tool_id": str(uuid.uuid4())}]},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_inheritance_two_levels(client):
    """customer→support→admin, admin has all tools."""
    agent = await _create_agent(client)
    t1 = await _create_tool(client, agent["id"], name=f"t1-{uuid.uuid4().hex[:8]}")
    t2 = await _create_tool(client, agent["id"], name=f"t2-{uuid.uuid4().hex[:8]}")
    t3 = await _create_tool(client, agent["id"], name=f"t3-{uuid.uuid4().hex[:8]}")

    customer = await _create_role(client, agent["id"], name=f"cust-{uuid.uuid4().hex[:8]}")
    support = await _create_role(client, agent["id"], name=f"sup-{uuid.uuid4().hex[:8]}", inherits_from=customer["id"])
    admin = await _create_role(client, agent["id"], name=f"adm-{uuid.uuid4().hex[:8]}", inherits_from=support["id"])

    # customer gets t1
    await client.put(
        f"/v1/agents/{agent['id']}/roles/{customer['id']}/permissions",
        json={"permissions": [{"tool_id": t1["id"]}]},
    )
    # support gets t2
    await client.put(
        f"/v1/agents/{agent['id']}/roles/{support['id']}/permissions",
        json={"permissions": [{"tool_id": t2["id"]}]},
    )
    # admin gets t3
    await client.put(
        f"/v1/agents/{agent['id']}/roles/{admin['id']}/permissions",
        json={"permissions": [{"tool_id": t3["id"]}]},
    )

    # Fetch admin role — should have t3 own + t1,t2 inherited
    resp = await client.get(f"/v1/agents/{agent['id']}/roles")
    roles = resp.json()
    admin_role = next(r for r in roles if r["id"] == admin["id"])
    assert len(admin_role["permissions"]) == 1  # own: t3
    assert len(admin_role["inherited_permissions"]) == 2  # inherited: t1, t2


@pytest.mark.asyncio
async def test_inheritance_child_override(client):
    """Child overrides parent scope for same tool."""
    agent = await _create_agent(client)
    tool = await _create_tool(client, agent["id"])

    parent = await _create_role(client, agent["id"], name=f"par-{uuid.uuid4().hex[:8]}")
    child = await _create_role(client, agent["id"], name=f"ch-{uuid.uuid4().hex[:8]}", inherits_from=parent["id"])

    # Parent: read scope
    await client.put(
        f"/v1/agents/{agent['id']}/roles/{parent['id']}/permissions",
        json={"permissions": [{"tool_id": tool["id"], "scopes": ["read"]}]},
    )
    # Child: read + write (override)
    await client.put(
        f"/v1/agents/{agent['id']}/roles/{child['id']}/permissions",
        json={"permissions": [{"tool_id": tool["id"], "scopes": ["read", "write"]}]},
    )

    # Child should have own permission (overriding parent), no inherited for this tool
    resp = await client.get(f"/v1/agents/{agent['id']}/roles")
    roles = resp.json()
    child_role = next(r for r in roles if r["id"] == child["id"])
    assert len(child_role["permissions"]) == 1
    assert child_role["permissions"][0]["scopes"] == ["read", "write"]
    # Not inherited since child overrides
    inherited_tool_ids = [p["tool_id"] for p in child_role["inherited_permissions"]]
    assert tool["id"] not in inherited_tool_ids


@pytest.mark.asyncio
async def test_default_deny(client):
    """Tool not in permission set → check returns DENY."""
    agent = await _create_agent(client)
    tool = await _create_tool(client, agent["id"], name=f"denied-{uuid.uuid4().hex[:8]}")
    role = await _create_role(client, agent["id"], name=f"norole-{uuid.uuid4().hex[:8]}")

    resp = await client.get(
        f"/v1/agents/{agent['id']}/check-permission",
        params={"role": role["name"], "tool": tool["name"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["allowed"] is False
    assert data["decision"] == "deny"


@pytest.mark.asyncio
async def test_check_permission_allow(client):
    """Role with permission → ALLOW."""
    agent = await _create_agent(client)
    tool = await _create_tool(client, agent["id"], name=f"allowed-{uuid.uuid4().hex[:8]}")
    role = await _create_role(client, agent["id"], name=f"ok-{uuid.uuid4().hex[:8]}")

    await client.put(
        f"/v1/agents/{agent['id']}/roles/{role['id']}/permissions",
        json={"permissions": [{"tool_id": tool["id"], "scopes": ["read"]}]},
    )

    resp = await client.get(
        f"/v1/agents/{agent['id']}/check-permission",
        params={"role": role["name"], "tool": tool["name"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["allowed"] is True
    assert data["decision"] == "allow"


@pytest.mark.asyncio
async def test_check_permission_deny(client):
    """Role without permission → DENY."""
    agent = await _create_agent(client)
    tool = await _create_tool(client, agent["id"], name=f"noaccess-{uuid.uuid4().hex[:8]}")
    role = await _create_role(client, agent["id"], name=f"noperm-{uuid.uuid4().hex[:8]}")

    resp = await client.get(
        f"/v1/agents/{agent['id']}/check-permission",
        params={"role": role["name"], "tool": tool["name"]},
    )
    data = resp.json()
    assert data["allowed"] is False
    assert data["decision"] == "deny"


@pytest.mark.asyncio
async def test_check_permission_inherited(client):
    """support inherits customer tools → customer tools return ALLOW."""
    agent = await _create_agent(client)
    tool = await _create_tool(client, agent["id"], name=f"cust-tool-{uuid.uuid4().hex[:8]}")

    customer = await _create_role(client, agent["id"], name=f"cust2-{uuid.uuid4().hex[:8]}")
    support = await _create_role(client, agent["id"], name=f"sup2-{uuid.uuid4().hex[:8]}", inherits_from=customer["id"])

    await client.put(
        f"/v1/agents/{agent['id']}/roles/{customer['id']}/permissions",
        json={"permissions": [{"tool_id": tool["id"]}]},
    )

    # Support should inherit access
    resp = await client.get(
        f"/v1/agents/{agent['id']}/check-permission",
        params={"role": support["name"], "tool": tool["name"]},
    )
    data = resp.json()
    assert data["allowed"] is True
    assert data["decision"] == "allow"


# ═══════════════════════════════════════════════════════════════════════
# 27c — Permission matrix (8 tests)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_matrix_empty(client):
    """No roles/tools → empty matrix."""
    agent = await _create_agent(client)
    resp = await client.get(f"/v1/agents/{agent['id']}/permission-matrix")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tools"] == []
    assert data["roles"] == []
    assert data["matrix"] == {}


@pytest.mark.asyncio
async def test_matrix_structure(client):
    """Has tools[], roles[], matrix{} keys."""
    agent = await _create_agent(client)
    await _create_tool(client, agent["id"])
    await _create_role(client, agent["id"])
    resp = await client.get(f"/v1/agents/{agent['id']}/permission-matrix")
    data = resp.json()
    assert "tools" in data
    assert "roles" in data
    assert "matrix" in data


@pytest.mark.asyncio
async def test_matrix_all_deny(client):
    """Role with no permissions → all 'deny'."""
    agent = await _create_agent(client)
    tool = await _create_tool(client, agent["id"], name=f"mt-{uuid.uuid4().hex[:8]}")
    role = await _create_role(client, agent["id"], name=f"mr-{uuid.uuid4().hex[:8]}")

    resp = await client.get(f"/v1/agents/{agent['id']}/permission-matrix")
    data = resp.json()
    assert data["matrix"][role["name"]][tool["name"]] == "deny"


@pytest.mark.asyncio
async def test_matrix_with_confirmation(client):
    """Tool requires_confirmation → 'confirm' in matrix."""
    agent = await _create_agent(client)
    tool = await _create_tool(
        client,
        agent["id"],
        name=f"conf-{uuid.uuid4().hex[:8]}",
        access_type="write",
        sensitivity="high",
    )
    role = await _create_role(client, agent["id"], name=f"confr-{uuid.uuid4().hex[:8]}")

    # Give permission
    await client.put(
        f"/v1/agents/{agent['id']}/roles/{role['id']}/permissions",
        json={"permissions": [{"tool_id": tool["id"]}]},
    )

    resp = await client.get(f"/v1/agents/{agent['id']}/permission-matrix")
    data = resp.json()
    assert data["matrix"][role["name"]][tool["name"]] == "confirm"


@pytest.mark.asyncio
async def test_matrix_inheritance_resolved(client):
    """Inherited permissions show as 'allow', not missing."""
    agent = await _create_agent(client)
    tool = await _create_tool(client, agent["id"], name=f"inh-{uuid.uuid4().hex[:8]}")

    parent = await _create_role(client, agent["id"], name=f"ipar-{uuid.uuid4().hex[:8]}")
    child = await _create_role(
        client,
        agent["id"],
        name=f"ich-{uuid.uuid4().hex[:8]}",
        inherits_from=parent["id"],
    )

    await client.put(
        f"/v1/agents/{agent['id']}/roles/{parent['id']}/permissions",
        json={"permissions": [{"tool_id": tool["id"]}]},
    )

    resp = await client.get(f"/v1/agents/{agent['id']}/permission-matrix")
    data = resp.json()
    # Child inherits parent's tool permission
    assert data["matrix"][child["name"]][tool["name"]] == "allow"


@pytest.mark.asyncio
async def test_matrix_matches_individual_checks(client):
    """Every cell in matrix matches individual check-permission call."""
    agent = await _create_agent(client)
    t1 = await _create_tool(client, agent["id"], name=f"mc1-{uuid.uuid4().hex[:8]}")
    t2 = await _create_tool(client, agent["id"], name=f"mc2-{uuid.uuid4().hex[:8]}")
    role = await _create_role(client, agent["id"], name=f"mcr-{uuid.uuid4().hex[:8]}")

    await client.put(
        f"/v1/agents/{agent['id']}/roles/{role['id']}/permissions",
        json={"permissions": [{"tool_id": t1["id"]}]},
    )

    resp = await client.get(f"/v1/agents/{agent['id']}/permission-matrix")
    matrix = resp.json()["matrix"]

    for tool_name in [t1["name"], t2["name"]]:
        check = await client.get(
            f"/v1/agents/{agent['id']}/check-permission",
            params={"role": role["name"], "tool": tool_name},
        )
        expected = matrix[role["name"]][tool_name]
        assert check.json()["decision"] == expected


@pytest.mark.asyncio
async def test_matrix_after_tool_delete(client):
    """Delete tool → matrix no longer includes it."""
    agent = await _create_agent(client)
    t1 = await _create_tool(client, agent["id"], name=f"del1-{uuid.uuid4().hex[:8]}")
    t2 = await _create_tool(client, agent["id"], name=f"del2-{uuid.uuid4().hex[:8]}")
    await _create_role(client, agent["id"])

    await client.delete(f"/v1/agents/{agent['id']}/tools/{t1['id']}")

    resp = await client.get(f"/v1/agents/{agent['id']}/permission-matrix")
    data = resp.json()
    assert t1["name"] not in data["tools"]
    assert t2["name"] in data["tools"]


@pytest.mark.asyncio
async def test_matrix_after_role_delete(client):
    """Delete role → matrix no longer includes it."""
    agent = await _create_agent(client)
    await _create_tool(client, agent["id"])
    r1 = await _create_role(client, agent["id"], name=f"rd1-{uuid.uuid4().hex[:8]}")
    r2 = await _create_role(client, agent["id"], name=f"rd2-{uuid.uuid4().hex[:8]}")

    await client.delete(f"/v1/agents/{agent['id']}/roles/{r1['id']}")

    resp = await client.get(f"/v1/agents/{agent['id']}/permission-matrix")
    data = resp.json()
    assert r1["name"] not in data["roles"]
    assert r2["name"] in data["roles"]


# ═══════════════════════════════════════════════════════════════════════
# 27d — Seed (6 tests)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_seed_creates_5_tools(client):
    """Reference agent has exactly 5 tools."""
    await seed_reference_agent()
    await seed_reference_tools_and_roles()

    # Find reference agent
    resp = await client.get("/v1/agents", params={"status": "active"})
    agents = resp.json()["items"]
    ref = next((a for a in agents if a["name"] == REFERENCE_AGENT["name"]), None)
    assert ref is not None

    resp = await client.get(f"/v1/agents/{ref['id']}/tools")
    assert len(resp.json()) == 5


@pytest.mark.asyncio
async def test_seed_creates_3_roles(client):
    """Reference agent has exactly 3 roles."""
    await seed_reference_agent()
    await seed_reference_tools_and_roles()

    resp = await client.get("/v1/agents", params={"status": "active"})
    ref = next(a for a in resp.json()["items"] if a["name"] == REFERENCE_AGENT["name"])

    resp = await client.get(f"/v1/agents/{ref['id']}/roles")
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_seed_inheritance_chain(client):
    """customer→support→admin chain correct."""
    await seed_reference_agent()
    await seed_reference_tools_and_roles()

    resp = await client.get("/v1/agents", params={"status": "active"})
    ref = next(a for a in resp.json()["items"] if a["name"] == REFERENCE_AGENT["name"])

    resp = await client.get(f"/v1/agents/{ref['id']}/roles")
    roles = {r["name"]: r for r in resp.json()}

    assert roles["customer"]["inherits_from"] is None
    assert roles["support"]["inherits_from"] == roles["customer"]["id"]
    assert roles["admin"]["inherits_from"] == roles["support"]["id"]


@pytest.mark.asyncio
async def test_seed_matrix_matches_existing_config(client):
    """Permission matrix matches existing rbac_config.yaml permissions."""
    await seed_reference_agent()
    await seed_reference_tools_and_roles()

    resp = await client.get("/v1/agents", params={"status": "active"})
    ref = next(a for a in resp.json()["items"] if a["name"] == REFERENCE_AGENT["name"])

    resp = await client.get(f"/v1/agents/{ref['id']}/permission-matrix")
    data = resp.json()
    matrix = data["matrix"]

    # customer: searchKB=allow, getOrderStatus=allow, rest=deny
    assert matrix["customer"]["searchKnowledgeBase"] == "allow"
    assert matrix["customer"]["getOrderStatus"] == "allow"
    assert matrix["customer"]["getCustomerProfile"] == "deny"
    assert matrix["customer"]["issueRefund"] == "deny"
    assert matrix["customer"]["getInternalSecrets"] == "deny"

    # support inherits customer + getCustomerProfile
    assert matrix["support"]["searchKnowledgeBase"] == "allow"
    assert matrix["support"]["getOrderStatus"] == "allow"
    assert matrix["support"]["getCustomerProfile"] == "allow"
    assert matrix["support"]["issueRefund"] == "deny"
    assert matrix["support"]["getInternalSecrets"] == "deny"

    # admin inherits support + issueRefund (confirm), getInternalSecrets
    assert matrix["admin"]["searchKnowledgeBase"] == "allow"
    assert matrix["admin"]["getOrderStatus"] == "allow"
    assert matrix["admin"]["getCustomerProfile"] == "allow"
    assert matrix["admin"]["issueRefund"] == "confirm"
    assert matrix["admin"]["getInternalSecrets"] == "allow"


@pytest.mark.asyncio
async def test_seed_idempotent(client):
    """Run seed twice → still 5 tools, 3 roles."""
    await seed_reference_agent()
    await seed_reference_tools_and_roles()
    await seed_reference_tools_and_roles()  # second time

    resp = await client.get("/v1/agents", params={"status": "active"})
    ref = next(a for a in resp.json()["items"] if a["name"] == REFERENCE_AGENT["name"])

    tools_resp = await client.get(f"/v1/agents/{ref['id']}/tools")
    assert len(tools_resp.json()) == 5

    roles_resp = await client.get(f"/v1/agents/{ref['id']}/roles")
    assert len(roles_resp.json()) == 3


@pytest.mark.asyncio
async def test_seed_check_permission_matches_legacy(client):
    """check_permission for key combos matches existing RBAC expectations."""
    await seed_reference_agent()
    await seed_reference_tools_and_roles()

    resp = await client.get("/v1/agents", params={"status": "active"})
    ref = next(a for a in resp.json()["items"] if a["name"] == REFERENCE_AGENT["name"])
    aid = ref["id"]

    # customer + issueRefund → deny
    r = await client.get(f"/v1/agents/{aid}/check-permission", params={"role": "customer", "tool": "issueRefund"})
    assert r.json()["decision"] == "deny"

    # admin + issueRefund → confirm (write+high)
    r = await client.get(f"/v1/agents/{aid}/check-permission", params={"role": "admin", "tool": "issueRefund"})
    assert r.json()["decision"] == "confirm"

    # support + searchKnowledgeBase → allow (inherited from customer)
    r = await client.get(
        f"/v1/agents/{aid}/check-permission", params={"role": "support", "tool": "searchKnowledgeBase"}
    )
    assert r.json()["decision"] == "allow"

    # customer + getInternalSecrets → deny
    r = await client.get(
        f"/v1/agents/{aid}/check-permission", params={"role": "customer", "tool": "getInternalSecrets"}
    )
    assert r.json()["decision"] == "deny"
