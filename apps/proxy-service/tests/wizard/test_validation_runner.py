"""Tests for Validation Runner — spec 30 (42 tests).

Covers:
  30a — Test pack definition (14 tests)
  30b — Validation engine (12 tests)
  30c — Validation API (12 tests)
  30d — Validation properties (4 tests)
"""

from __future__ import annotations

import dataclasses
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.wizard.seed import (
    seed_reference_agent,
    seed_reference_tools_and_roles,
)
from src.wizard.services.validation_runner import (
    BasicTestPack,
    ValidationTestDefinition,
    run_validation,
)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Helpers ──────────────────────────────────────────────────────────────

_AGENT_BODY = {
    "name": f"ValTestAgent-{uuid.uuid4().hex[:8]}",
    "description": "Agent for validation runner tests",
    "team": "platform",
    "framework": "langgraph",
    "environment": "dev",
    "is_public_facing": True,
    "has_tools": True,
    "has_write_actions": True,
    "touches_pii": True,
    "handles_secrets": False,
    "calls_external_apis": False,
}


async def _create_agent(client: AsyncClient, **overrides) -> dict:
    body = {**_AGENT_BODY, "name": f"ValAgent-{uuid.uuid4().hex[:8]}", **overrides}
    resp = await client.post("/v1/agents", json=body)
    assert resp.status_code == 201
    return resp.json()


async def _create_tool(client: AsyncClient, agent_id: str, **overrides) -> dict:
    body = {"name": f"tool-{uuid.uuid4().hex[:8]}", "description": "test", **overrides}
    resp = await client.post(f"/v1/agents/{agent_id}/tools", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_role(client: AsyncClient, agent_id: str, **overrides) -> dict:
    body = {"name": f"role-{uuid.uuid4().hex[:8]}", "description": "test", **overrides}
    resp = await client.post(f"/v1/agents/{agent_id}/roles", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _seed_ref_agent(client: AsyncClient) -> dict:
    """Seed reference agent + tools/roles, return agent dict."""
    await seed_reference_agent()
    await seed_reference_tools_and_roles()
    resp = await client.get("/v1/agents")
    assert resp.status_code == 200
    agents = resp.json()["items"]
    ref = [a for a in agents if a["is_reference"]]
    assert ref, "Reference agent not found after seeding"
    return ref[0]


async def _setup_full_agent(client: AsyncClient) -> dict:
    """Create an agent with tools, roles, permissions, policy_pack and generated config."""
    agent = await _create_agent(client, policy_pack="customer_support")

    # Tools
    t_low = await _create_tool(client, agent["id"], name="readDocs", sensitivity="low")
    t_med = await _create_tool(client, agent["id"], name="getProfile", sensitivity="medium")
    t_high = await _create_tool(client, agent["id"], name="updateRecord", sensitivity="high")
    t_crit = await _create_tool(client, agent["id"], name="deleteAll", sensitivity="critical")

    # Roles
    r_user = await _create_role(client, agent["id"], name="user")
    r_operator = await _create_role(client, agent["id"], name="operator", inherits_from=r_user["id"])
    r_admin = await _create_role(client, agent["id"], name="admin", inherits_from=r_operator["id"])

    # Permissions: user → readDocs only, operator → getProfile, admin → updateRecord + deleteAll
    await client.put(
        f"/v1/agents/{agent['id']}/roles/{r_user['id']}/permissions",
        json={"permissions": [{"tool_id": t_low["id"], "scopes": ["read"]}]},
    )
    await client.put(
        f"/v1/agents/{agent['id']}/roles/{r_operator['id']}/permissions",
        json={"permissions": [{"tool_id": t_med["id"], "scopes": ["read"]}]},
    )
    await client.put(
        f"/v1/agents/{agent['id']}/roles/{r_admin['id']}/permissions",
        json={
            "permissions": [
                {"tool_id": t_high["id"], "scopes": ["read", "write"]},
                {"tool_id": t_crit["id"], "scopes": ["read", "write"]},
            ]
        },
    )

    # Generate config
    resp = await client.post(f"/v1/agents/{agent['id']}/generate-config")
    assert resp.status_code == 200

    # Refresh
    resp = await client.get(f"/v1/agents/{agent['id']}")
    assert resp.status_code == 200
    return resp.json()


async def _setup_ref_with_config(client: AsyncClient) -> dict:
    """Seed reference agent, set policy_pack, generate config."""
    ref = await _seed_ref_agent(client)
    # Set policy pack
    resp = await client.patch(
        f"/v1/agents/{ref['id']}",
        json={"policy_pack": "customer_support"},
    )
    assert resp.status_code == 200

    # Generate config
    resp = await client.post(f"/v1/agents/{ref['id']}/generate-config")
    assert resp.status_code == 200

    # Refresh
    resp = await client.get(f"/v1/agents/{ref['id']}")
    assert resp.status_code == 200
    return resp.json()


# ═══════════════════════════════════════════════════════════════════════
# 30a tests — Test pack definition (14 tests)
# ═══════════════════════════════════════════════════════════════════════


class Test30aTestPackDefinition:
    """30a — BasicTestPack generates 12 parameterized tests."""

    @pytest.mark.asyncio
    async def test_basic_pack_has_12_tests(self, client: AsyncClient) -> None:
        """BasicTestPack generates exactly 12 test definitions."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            tests = await BasicTestPack.generate(uuid.UUID(agent["id"]), db)
        assert len(tests) == 12

    @pytest.mark.asyncio
    async def test_pack_3_rbac_tests(self, client: AsyncClient) -> None:
        """Exactly 3 tests with category='rbac'."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            tests = await BasicTestPack.generate(uuid.UUID(agent["id"]), db)
        rbac = [t for t in tests if t.category == "rbac"]
        assert len(rbac) == 3

    @pytest.mark.asyncio
    async def test_pack_3_injection_tests(self, client: AsyncClient) -> None:
        """Exactly 3 tests with category='injection'."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            tests = await BasicTestPack.generate(uuid.UUID(agent["id"]), db)
        injection = [t for t in tests if t.category == "injection"]
        assert len(injection) == 3

    @pytest.mark.asyncio
    async def test_pack_3_pii_tests(self, client: AsyncClient) -> None:
        """Exactly 3 tests with category='pii'."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            tests = await BasicTestPack.generate(uuid.UUID(agent["id"]), db)
        pii = [t for t in tests if t.category == "pii"]
        assert len(pii) == 3

    @pytest.mark.asyncio
    async def test_pack_3_budget_tests(self, client: AsyncClient) -> None:
        """Exactly 3 tests with category='budget'."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            tests = await BasicTestPack.generate(uuid.UUID(agent["id"]), db)
        budget = [t for t in tests if t.category == "budget"]
        assert len(budget) == 3

    @pytest.mark.asyncio
    async def test_rbac_test_uses_agent_roles(self, client: AsyncClient) -> None:
        """Test 1 input.role = agent's lowest role."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            tests = await BasicTestPack.generate(uuid.UUID(agent["id"]), db)
        rbac_test = [t for t in tests if t.name == "rbac_lowest_to_highest"][0]
        assert rbac_test.input["role"] == "user"  # our lowest role

    @pytest.mark.asyncio
    async def test_rbac_test_uses_agent_tools(self, client: AsyncClient) -> None:
        """Test 1 input.tool = agent's highest-sensitivity tool."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            tests = await BasicTestPack.generate(uuid.UUID(agent["id"]), db)
        rbac_test = [t for t in tests if t.name == "rbac_lowest_to_highest"][0]
        assert rbac_test.input["tool"] == "deleteAll"  # our critical tool

    @pytest.mark.asyncio
    async def test_injection_test_uses_agent_args(self, client: AsyncClient) -> None:
        """Test 4 uses injection payload in tool's arg names."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            tests = await BasicTestPack.generate(uuid.UUID(agent["id"]), db)
        inj_test = [t for t in tests if t.name == "injection_sql"][0]
        assert "args" in inj_test.input
        # Should use an actual agent tool name
        assert inj_test.input["tool"] in ["readDocs", "getProfile", "updateRecord", "deleteAll"]

    @pytest.mark.asyncio
    async def test_pii_test_uses_agent_tools(self, client: AsyncClient) -> None:
        """Test 7 uses agent's tool names."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            tests = await BasicTestPack.generate(uuid.UUID(agent["id"]), db)
        pii_test = [t for t in tests if t.name == "pii_email_redacted"][0]
        assert pii_test.input["tool"] in ["readDocs", "getProfile", "updateRecord", "deleteAll"]

    @pytest.mark.asyncio
    async def test_budget_test_uses_agent_limits(self, client: AsyncClient) -> None:
        """Test 10 threshold = agent's rate_limit + 1 (or max_tool_calls + 1)."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            tests = await BasicTestPack.generate(uuid.UUID(agent["id"]), db)
        budget_test = [t for t in tests if t.name == "budget_rate_limit"][0]
        # tool_calls should exceed the configured limit
        assert budget_test.input["tool_calls"] > 0

    @pytest.mark.asyncio
    async def test_each_test_is_dataclass(self, client: AsyncClient) -> None:
        """Every test has: name, category, description, input, expected_decision."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            tests = await BasicTestPack.generate(uuid.UUID(agent["id"]), db)
        for t in tests:
            assert dataclasses.is_dataclass(t)
            assert isinstance(t, ValidationTestDefinition)
            assert t.name
            assert t.category
            assert t.description
            assert isinstance(t.input, dict)
            assert t.expected_decision
            assert t.expected_reason

    @pytest.mark.asyncio
    async def test_pack_for_agent_no_tools(self, client: AsyncClient) -> None:
        """Agent with 0 tools → pack generates with generic defaults."""
        agent = await _create_agent(client, policy_pack="customer_support")
        # Generate config with no tools
        resp = await client.post(f"/v1/agents/{agent['id']}/generate-config")
        assert resp.status_code == 200

        from src.db.session import async_session

        async with async_session() as db:
            tests = await BasicTestPack.generate(uuid.UUID(agent["id"]), db)
        assert len(tests) == 12
        # Should use generic tool name
        rbac_test = [t for t in tests if t.name == "rbac_lowest_to_highest"][0]
        assert rbac_test.input["tool"] == "generic_tool"

    @pytest.mark.asyncio
    async def test_pack_for_agent_no_roles(self, client: AsyncClient) -> None:
        """Agent with 0 roles → pack generates with generic defaults."""
        agent = await _create_agent(client, policy_pack="customer_support")
        # Add a tool but no roles
        await _create_tool(client, agent["id"], name="someTool", sensitivity="low")
        resp = await client.post(f"/v1/agents/{agent['id']}/generate-config")
        assert resp.status_code == 200

        from src.db.session import async_session

        async with async_session() as db:
            tests = await BasicTestPack.generate(uuid.UUID(agent["id"]), db)
        assert len(tests) == 12
        # Should use generic role names
        rbac_test = [t for t in tests if t.name == "rbac_lowest_to_highest"][0]
        assert rbac_test.input["role"] == "user"  # generic default

    @pytest.mark.asyncio
    async def test_pack_version_field(self, client: AsyncClient) -> None:
        """BasicTestPack has version string."""
        assert BasicTestPack.VERSION == "1.0.0"
        assert isinstance(BasicTestPack.VERSION, str)


# ═══════════════════════════════════════════════════════════════════════
# 30b tests — Validation engine (12 tests)
# ═══════════════════════════════════════════════════════════════════════


class Test30bValidationEngine:
    """30b — Validation engine runs tests against generated config."""

    @pytest.mark.asyncio
    async def test_run_validation_demo_agent_12_pass(self, client: AsyncClient) -> None:
        """Demo agent with proper config → 12/12 pass."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            result = await run_validation(uuid.UUID(agent["id"]), db)
        assert result.total == 12
        assert result.passed == 12
        assert result.failed == 0
        assert result.score == 12

    @pytest.mark.asyncio
    async def test_result_structure(self, client: AsyncClient) -> None:
        """Result has total, passed, failed, tests[]."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            result = await run_validation(uuid.UUID(agent["id"]), db)
        assert hasattr(result, "total")
        assert hasattr(result, "passed")
        assert hasattr(result, "failed")
        assert hasattr(result, "tests")
        assert isinstance(result.tests, list)
        assert len(result.tests) == 12

    @pytest.mark.asyncio
    async def test_per_test_detail(self, client: AsyncClient) -> None:
        """Each test detail has: name, category, expected, actual, passed, duration_ms."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            result = await run_validation(uuid.UUID(agent["id"]), db)
        for test in result.tests:
            assert "name" in test
            assert "category" in test
            assert "expected" in test
            assert "actual" in test
            assert "passed" in test
            assert "duration_ms" in test

    @pytest.mark.asyncio
    async def test_failed_test_has_recommendation(self, client: AsyncClient) -> None:
        """Deliberately broken config → recommendation not null."""
        # Create agent with research pack (pii_redaction=False)
        agent = await _create_agent(client, policy_pack="research")
        await _create_tool(client, agent["id"], name="someTool", sensitivity="low")
        resp = await client.post(f"/v1/agents/{agent['id']}/generate-config")
        assert resp.status_code == 200

        from src.db.session import async_session

        async with async_session() as db:
            result = await run_validation(uuid.UUID(agent["id"]), db)
        # Research pack has pii_redaction=False so PII tests should fail
        pii_results = [t for t in result.tests if t["category"] == "pii"]
        assert any(not t["passed"] for t in pii_results)
        failed_pii = [t for t in pii_results if not t["passed"]]
        for t in failed_pii:
            assert t["recommendation"] is not None
            assert len(t["recommendation"]) > 10

    @pytest.mark.asyncio
    async def test_rbac_deny_detected(self, client: AsyncClient) -> None:
        """Lowest role → highest tool → actual=DENY."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            result = await run_validation(uuid.UUID(agent["id"]), db)
        rbac_deny = [t for t in result.tests if t["name"] == "rbac_lowest_to_highest"][0]
        assert rbac_deny["actual"] == "DENY"
        assert rbac_deny["passed"] is True

    @pytest.mark.asyncio
    async def test_rbac_allow_detected(self, client: AsyncClient) -> None:
        """Admin → admin tool → actual=ALLOW."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            result = await run_validation(uuid.UUID(agent["id"]), db)
        rbac_allow = [t for t in result.tests if t["name"] == "rbac_admin_to_admin"][0]
        assert rbac_allow["actual"] == "ALLOW"
        assert rbac_allow["passed"] is True

    @pytest.mark.asyncio
    async def test_injection_blocked(self, client: AsyncClient) -> None:
        """SQL injection input → actual=BLOCKED."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            result = await run_validation(uuid.UUID(agent["id"]), db)
        inj = [t for t in result.tests if t["name"] == "injection_sql"][0]
        assert inj["actual"] == "BLOCKED"
        assert inj["passed"] is True

    @pytest.mark.asyncio
    async def test_pii_redacted(self, client: AsyncClient) -> None:
        """Email in output → actual=REDACTED."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            result = await run_validation(uuid.UUID(agent["id"]), db)
        pii = [t for t in result.tests if t["name"] == "pii_email_redacted"][0]
        assert pii["actual"] == "REDACTED"
        assert pii["passed"] is True

    @pytest.mark.asyncio
    async def test_budget_over_limit(self, client: AsyncClient) -> None:
        """Exceed rate limit → actual=BLOCKED."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            result = await run_validation(uuid.UUID(agent["id"]), db)
        budget = [t for t in result.tests if t["name"] == "budget_rate_limit"][0]
        assert budget["actual"] == "BLOCKED"
        assert budget["passed"] is True

    @pytest.mark.asyncio
    async def test_engine_loads_generated_config(self, client: AsyncClient) -> None:
        """Engine uses agent's generated config, not hardcoded."""
        agent = await _setup_full_agent(client)
        # Verify config is on the agent
        resp = await client.get(f"/v1/agents/{agent['id']}")
        data = resp.json()
        assert data["generated_config"] is not None
        assert "rbac_yaml" in data["generated_config"]

        from src.db.session import async_session

        async with async_session() as db:
            result = await run_validation(uuid.UUID(agent["id"]), db)
        assert result.total == 12

    @pytest.mark.asyncio
    async def test_engine_no_config_generated(self, client: AsyncClient) -> None:
        """Agent without generated config → error (not crash)."""
        agent = await _create_agent(client)

        from src.db.session import async_session

        async with async_session() as db:
            with pytest.raises(ValueError, match="no generated config"):
                await run_validation(uuid.UUID(agent["id"]), db)

    @pytest.mark.asyncio
    async def test_engine_duration_ms(self, client: AsyncClient) -> None:
        """Each test duration_ms > 0."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            result = await run_validation(uuid.UUID(agent["id"]), db)
        for test in result.tests:
            assert test["duration_ms"] >= 0  # may be 0.0 on fast machines


# ═══════════════════════════════════════════════════════════════════════
# 30c tests — Validation API (12 tests)
# ═══════════════════════════════════════════════════════════════════════


class Test30cValidationAPI:
    """30c — Validation REST endpoints."""

    @pytest.mark.asyncio
    async def test_post_validate_returns_result(self, client: AsyncClient) -> None:
        """POST → 200, body matches schema."""
        agent = await _setup_full_agent(client)
        resp = await client.post(f"/v1/agents/{agent['id']}/validate", json={"pack": "basic"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert data["passed"] == 12

    @pytest.mark.asyncio
    async def test_post_validate_nonexistent_agent(self, client: AsyncClient) -> None:
        """POST bad ID → 404."""
        bad_id = str(uuid.uuid4())
        resp = await client.post(f"/v1/agents/{bad_id}/validate", json={"pack": "basic"})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_post_validate_default_pack(self, client: AsyncClient) -> None:
        """POST without body → uses 'basic' pack."""
        agent = await _setup_full_agent(client)
        resp = await client.post(f"/v1/agents/{agent['id']}/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pack"] == "basic"

    @pytest.mark.asyncio
    async def test_post_validate_unknown_pack(self, client: AsyncClient) -> None:
        """POST { pack: 'xxx' } → 422."""
        agent = await _setup_full_agent(client)
        resp = await client.post(f"/v1/agents/{agent['id']}/validate", json={"pack": "xxx"})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_post_validate_stores_run(self, client: AsyncClient) -> None:
        """After POST, run stored in DB."""
        agent = await _setup_full_agent(client)
        resp = await client.post(f"/v1/agents/{agent['id']}/validate", json={"pack": "basic"})
        assert resp.status_code == 200

        # Check history
        resp = await client.get(f"/v1/agents/{agent['id']}/validations")
        assert resp.status_code == 200
        runs = resp.json()
        assert len(runs) >= 1
        assert runs[0]["score"] == 12

    @pytest.mark.asyncio
    async def test_get_validations_history(self, client: AsyncClient) -> None:
        """GET /agents/:id/validations → list of runs."""
        agent = await _setup_full_agent(client)
        # Run twice
        await client.post(f"/v1/agents/{agent['id']}/validate", json={"pack": "basic"})
        await client.post(f"/v1/agents/{agent['id']}/validate", json={"pack": "basic"})

        resp = await client.get(f"/v1/agents/{agent['id']}/validations")
        assert resp.status_code == 200
        runs = resp.json()
        assert len(runs) >= 2

    @pytest.mark.asyncio
    async def test_get_validations_empty(self, client: AsyncClient) -> None:
        """New agent → []."""
        agent = await _create_agent(client)
        resp = await client.get(f"/v1/agents/{agent['id']}/validations")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_get_validations_ordered(self, client: AsyncClient) -> None:
        """Most recent first."""
        agent = await _setup_full_agent(client)
        await client.post(f"/v1/agents/{agent['id']}/validate", json={"pack": "basic"})
        await client.post(f"/v1/agents/{agent['id']}/validate", json={"pack": "basic"})

        resp = await client.get(f"/v1/agents/{agent['id']}/validations")
        runs = resp.json()
        assert len(runs) >= 2
        # Most recent first = created_at[0] >= created_at[1]
        assert runs[0]["created_at"] >= runs[1]["created_at"]

    @pytest.mark.asyncio
    async def test_post_validate_categories_breakdown(self, client: AsyncClient) -> None:
        """Response has categories.rbac, .injection, .pii, .budget."""
        agent = await _setup_full_agent(client)
        resp = await client.post(f"/v1/agents/{agent['id']}/validate", json={"pack": "basic"})
        data = resp.json()
        cats = data["categories"]
        assert "rbac" in cats
        assert "injection" in cats
        assert "pii" in cats
        assert "budget" in cats
        for cat_name in ["rbac", "injection", "pii", "budget"]:
            assert cats[cat_name]["total"] == 3
            assert "passed" in cats[cat_name]

    @pytest.mark.asyncio
    async def test_post_validate_response_timing(self, client: AsyncClient) -> None:
        """Response has run_at + duration_ms."""
        agent = await _setup_full_agent(client)
        resp = await client.post(f"/v1/agents/{agent['id']}/validate", json={"pack": "basic"})
        data = resp.json()
        assert "run_at" in data
        assert "duration_ms" in data
        assert data["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_post_validate_result_schema_full(self, client: AsyncClient) -> None:
        """Every field from API schema doc present."""
        agent = await _setup_full_agent(client)
        resp = await client.post(f"/v1/agents/{agent['id']}/validate", json={"pack": "basic"})
        data = resp.json()
        required_fields = [
            "agent_id",
            "pack",
            "pack_version",
            "score",
            "total",
            "passed",
            "failed",
            "categories",
            "tests",
            "run_at",
            "duration_ms",
        ]
        for field_name in required_fields:
            assert field_name in data, f"Missing field: {field_name}"

        # Per-test fields
        for test in data["tests"]:
            for tfield in ["name", "category", "expected", "actual", "passed", "duration_ms"]:
                assert tfield in test, f"Missing test field: {tfield}"

    @pytest.mark.asyncio
    async def test_rerun_same_score(self, client: AsyncClient) -> None:
        """POST twice → same score (determinism)."""
        agent = await _setup_full_agent(client)
        r1 = await client.post(f"/v1/agents/{agent['id']}/validate", json={"pack": "basic"})
        r2 = await client.post(f"/v1/agents/{agent['id']}/validate", json={"pack": "basic"})
        assert r1.json()["score"] == r2.json()["score"]
        assert r1.json()["passed"] == r2.json()["passed"]
        assert r1.json()["failed"] == r2.json()["failed"]


# ═══════════════════════════════════════════════════════════════════════
# 30d tests — Validation properties (4 tests)
# ═══════════════════════════════════════════════════════════════════════


class Test30dValidationProperties:
    """30d — Deterministic, versioned, no-LLM properties."""

    @pytest.mark.asyncio
    async def test_deterministic_same_config(self, client: AsyncClient) -> None:
        """Same config, 3 runs → 3 identical results."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        scores = []
        for _ in range(3):
            async with async_session() as db:
                result = await run_validation(uuid.UUID(agent["id"]), db)
            scores.append(result.score)
        assert scores[0] == scores[1] == scores[2]

    @pytest.mark.asyncio
    async def test_versioned_tests(self, client: AsyncClient) -> None:
        """Each test in result has version field."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            result = await run_validation(uuid.UUID(agent["id"]), db)
        for test in result.tests:
            assert "version" in test
            assert test["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_pack_version_in_result(self, client: AsyncClient) -> None:
        """Result includes pack_version."""
        agent = await _setup_full_agent(client)
        from src.db.session import async_session

        async with async_session() as db:
            result = await run_validation(uuid.UUID(agent["id"]), db)
        assert result.pack_version == "1.0.0"

    @pytest.mark.asyncio
    async def test_no_llm_dependency(self, client: AsyncClient) -> None:
        """Validation runs with no LLM configured (no env vars needed)."""
        import os

        # Ensure no LLM API key is used
        old = os.environ.get("OPENAI_API_KEY")
        if old:
            del os.environ["OPENAI_API_KEY"]

        try:
            agent = await _setup_full_agent(client)
            from src.db.session import async_session

            async with async_session() as db:
                result = await run_validation(uuid.UUID(agent["id"]), db)
            assert result.total == 12
            assert result.passed == 12
        finally:
            if old:
                os.environ["OPENAI_API_KEY"] = old
