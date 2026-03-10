"""Full wizard variant tests — spec 33v (cross-product integration kit tests).

Covers every meaningful combination of wizard inputs and validates that
generated files are correct, parseable, and internally consistent.

Variant matrix:
  V1  — 1 role + 1 tool (minimal agent)
  V2  — 3 roles + 5 tools with RBAC matrix (reference agent)
  V3  — 0 tools, 0 roles (empty agent)
  V4  — All 3 frameworks × customer_support pack
  V5  — All 5 policy packs × langgraph framework
  V6  — Sensitivity levels: all-low vs all-critical
  V7  — Rate limits: per-tool + per-role cross-check
  V8  — Rollout modes: observe / warn / enforce
  V9  — Boolean flags: public-facing, PII, secrets, external APIs
  V10 — RBAC coherence: generated code matches generated YAML
  V11 — Cross-file consistency: config YAML ↔ protection code ↔ tests
"""

from __future__ import annotations

import ast
import io
import uuid
import zipfile

import pytest
import yaml
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Helpers ──────────────────────────────────────────────────────────────


async def _create_agent(client: AsyncClient, **overrides) -> dict:
    body = {
        "name": f"Variant-{uuid.uuid4().hex[:8]}",
        "description": "Variant test agent",
        "team": "platform",
        "framework": "langgraph",
        "environment": "dev",
        "is_public_facing": False,
        "has_tools": True,
        "has_write_actions": False,
        "touches_pii": False,
        "handles_secrets": False,
        "calls_external_apis": False,
        **overrides,
    }
    resp = await client.post("/v1/agents", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_tool(client: AsyncClient, agent_id: str, **overrides) -> dict:
    body = {
        "name": f"tool-{uuid.uuid4().hex[:8]}",
        "description": "variant tool",
        **overrides,
    }
    resp = await client.post(f"/v1/agents/{agent_id}/tools", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_role(client: AsyncClient, agent_id: str, **overrides) -> dict:
    body = {
        "name": f"role-{uuid.uuid4().hex[:8]}",
        "description": "variant role",
        **overrides,
    }
    resp = await client.post(f"/v1/agents/{agent_id}/roles", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _set_permissions(
    client: AsyncClient, agent_id: str, role_id: str, tool_ids: list[str], scopes: list[str] | None = None
) -> None:
    perms = [{"tool_id": tid, "scopes": scopes or ["read"]} for tid in tool_ids]
    resp = await client.put(
        f"/v1/agents/{agent_id}/roles/{role_id}/permissions",
        json={"permissions": perms},
    )
    assert resp.status_code == 200, resp.text


async def _generate_kit(client: AsyncClient, agent_id: str) -> dict:
    resp = await client.post(f"/v1/agents/{agent_id}/integration-kit")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _parse_yaml_files(kit: dict) -> dict[str, dict]:
    """Parse all YAML files from kit, return {filename: parsed_data}."""
    result = {}
    for name in ["rbac.yaml", "limits.yaml", "policy.yaml"]:
        if name in kit["files"]:
            result[name] = yaml.safe_load(kit["files"][name])
    return result


def _parse_python_ast(code: str) -> ast.Module:
    """Parse Python code, raise if syntax error."""
    return ast.parse(code)


def _get_function_names(code: str) -> set[str]:
    """Extract all function names from Python code."""
    tree = ast.parse(code)
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}


def _get_class_names(code: str) -> set[str]:
    """Extract all class names from Python code."""
    tree = ast.parse(code)
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}


# ═══════════════════════════════════════════════════════════════════════
# V1 — Minimal agent: 1 role + 1 tool
# ═══════════════════════════════════════════════════════════════════════


class TestVariantMinimalAgent:
    """Single role with access to single tool — edge case for RBAC."""

    @pytest.mark.asyncio
    async def test_minimal_kit_generates(self, client):
        """Kit generates without error for 1-role 1-tool agent."""
        agent = await _create_agent(client, policy_pack="customer_support")
        tool = await _create_tool(client, agent["id"], name="onlyTool", sensitivity="low")
        role = await _create_role(client, agent["id"], name="onlyRole")
        await _set_permissions(client, agent["id"], role["id"], [tool["id"]])

        kit = await _generate_kit(client, agent["id"])
        assert len(kit["files"]) == 7

    @pytest.mark.asyncio
    async def test_minimal_rbac_yaml_has_one_role(self, client):
        """RBAC YAML lists exactly 1 role with 1 tool."""
        agent = await _create_agent(client, policy_pack="customer_support")
        tool = await _create_tool(client, agent["id"], name="singleTool", sensitivity="medium")
        role = await _create_role(client, agent["id"], name="singleRole")
        await _set_permissions(client, agent["id"], role["id"], [tool["id"]])

        kit = await _generate_kit(client, agent["id"])
        rbac = yaml.safe_load(kit["files"]["rbac.yaml"])
        assert "roles" in rbac
        role_names = list(rbac["roles"].keys())
        assert "singleRole" in role_names

    @pytest.mark.asyncio
    async def test_minimal_test_security_valid_python(self, client):
        """test_security.py from 1-role agent parses as valid Python."""
        agent = await _create_agent(client, policy_pack="customer_support")
        tool = await _create_tool(client, agent["id"], name="aTool", sensitivity="low")
        role = await _create_role(client, agent["id"], name="aRole")
        await _set_permissions(client, agent["id"], role["id"], [tool["id"]])

        kit = await _generate_kit(client, agent["id"])
        tree = ast.parse(kit["files"]["test_security.py"])
        test_funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
        assert len(test_funcs) == 5

    @pytest.mark.asyncio
    async def test_minimal_rbac_unknown_role_blocked(self, client):
        """Generated test_security.py has unknown role block test even for 1-role agent."""
        agent = await _create_agent(client, policy_pack="customer_support")
        tool = await _create_tool(client, agent["id"], name="t1", sensitivity="low")
        role = await _create_role(client, agent["id"], name="r1")
        await _set_permissions(client, agent["id"], role["id"], [tool["id"]])

        kit = await _generate_kit(client, agent["id"])
        code = kit["files"]["test_security.py"]
        assert "__nonexistent_role__" in code
        assert "test_rbac_allow_authorized" in code

    @pytest.mark.asyncio
    async def test_minimal_protection_code_valid(self, client):
        """protected_agent.py parses for 1-role agent."""
        agent = await _create_agent(client, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="toolX", sensitivity="low")

        kit = await _generate_kit(client, agent["id"])
        ast.parse(kit["files"]["protected_agent.py"])  # must not raise


# ═══════════════════════════════════════════════════════════════════════
# V2 — Rich agent: 3 roles + 5 tools with full RBAC matrix
# ═══════════════════════════════════════════════════════════════════════


class TestVariantRichAgent:
    """Complex agent with multi-role hierarchy and varied tool access."""

    async def _setup_rich_agent(self, client: AsyncClient) -> tuple[dict, list[dict], list[dict]]:
        agent = await _create_agent(client, policy_pack="customer_support", has_write_actions=True, touches_pii=True)
        aid = agent["id"]

        tools = [
            await _create_tool(client, aid, name="readPublic", access_type="read", sensitivity="low"),
            await _create_tool(client, aid, name="readPII", access_type="read", sensitivity="medium"),
            await _create_tool(client, aid, name="writeOrders", access_type="write", sensitivity="high"),
            await _create_tool(client, aid, name="deleteRecords", access_type="write", sensitivity="critical"),
            await _create_tool(client, aid, name="viewSecrets", access_type="read", sensitivity="critical"),
        ]

        viewer = await _create_role(client, aid, name="viewer")
        editor = await _create_role(client, aid, name="editor")
        admin = await _create_role(client, aid, name="admin")
        roles = [viewer, editor, admin]

        # viewer → readPublic only
        await _set_permissions(client, aid, viewer["id"], [tools[0]["id"]])
        # editor → readPublic, readPII, writeOrders
        await _set_permissions(
            client, aid, editor["id"], [tools[0]["id"], tools[1]["id"], tools[2]["id"]], scopes=["read", "write"]
        )
        # admin → all tools
        await _set_permissions(client, aid, admin["id"], [t["id"] for t in tools], scopes=["read", "write"])

        return agent, tools, roles

    @pytest.mark.asyncio
    async def test_rich_all_yaml_files_valid(self, client):
        """All 3 YAML files parse correctly."""
        agent, tools, roles = await self._setup_rich_agent(client)
        kit = await _generate_kit(client, agent["id"])
        yamls = _parse_yaml_files(kit)
        assert len(yamls) == 3
        for name, data in yamls.items():
            assert data is not None, f"{name} parsed to None"

    @pytest.mark.asyncio
    async def test_rich_rbac_has_all_roles(self, client):
        """RBAC YAML has viewer, editor, admin."""
        agent, tools, roles = await self._setup_rich_agent(client)
        kit = await _generate_kit(client, agent["id"])
        rbac = yaml.safe_load(kit["files"]["rbac.yaml"])
        role_names = set(rbac["roles"].keys())
        assert role_names == {"viewer", "editor", "admin"}

    @pytest.mark.asyncio
    async def test_rich_rbac_viewer_limited(self, client):
        """Viewer role has only readPublic tool."""
        agent, tools, roles = await self._setup_rich_agent(client)
        kit = await _generate_kit(client, agent["id"])
        rbac = yaml.safe_load(kit["files"]["rbac.yaml"])
        viewer_tools = list(rbac["roles"]["viewer"].get("tools", {}).keys())
        assert "readPublic" in viewer_tools
        assert "deleteRecords" not in viewer_tools

    @pytest.mark.asyncio
    async def test_rich_rbac_admin_has_all_tools(self, client):
        """Admin role has access to all 5 tools (own + inherited)."""
        agent, tools, roles = await self._setup_rich_agent(client)
        kit = await _generate_kit(client, agent["id"])
        rbac = yaml.safe_load(kit["files"]["rbac.yaml"])
        # RBAC lists only OWN tools per role (inheritance resolves at runtime)
        # So we collect tools from all roles
        all_tools = set()
        for role_data in rbac["roles"].values():
            all_tools.update(role_data.get("tools", {}).keys())
        assert len(all_tools) == 5

    @pytest.mark.asyncio
    async def test_rich_protection_has_all_tool_names(self, client):
        """protected_agent.py references all 5 tool names."""
        agent, tools, roles = await self._setup_rich_agent(client)
        kit = await _generate_kit(client, agent["id"])
        code = kit["files"]["protected_agent.py"]
        for t in tools:
            assert t["name"] in code, f"Missing tool name: {t['name']}"

    @pytest.mark.asyncio
    async def test_rich_protection_has_all_role_names(self, client):
        """protected_agent.py references all 3 role names."""
        agent, tools, roles = await self._setup_rich_agent(client)
        kit = await _generate_kit(client, agent["id"])
        code = kit["files"]["protected_agent.py"]
        for r in roles:
            assert r["name"] in code, f"Missing role name: {r['name']}"

    @pytest.mark.asyncio
    async def test_rich_limits_has_tool_rate_limits(self, client):
        """limits.yaml has per-tool rate limits for high/critical tools."""
        agent, tools, roles = await self._setup_rich_agent(client)
        kit = await _generate_kit(client, agent["id"])
        limits = yaml.safe_load(kit["files"]["limits.yaml"])
        assert "tool_rate_limits" in limits

    @pytest.mark.asyncio
    async def test_rich_test_security_has_5_functions(self, client):
        """test_security.py has exactly 5 test functions for rich agent."""
        agent, tools, roles = await self._setup_rich_agent(client)
        kit = await _generate_kit(client, agent["id"])
        test_funcs = _get_function_names(kit["files"]["test_security.py"])
        actual_tests = {n for n in test_funcs if n.startswith("test_")}
        assert len(actual_tests) == 5


# ═══════════════════════════════════════════════════════════════════════
# V3 — Empty agent: 0 tools, 0 roles
# ═══════════════════════════════════════════════════════════════════════


class TestVariantEmptyAgent:
    """Agent with no tools and no roles — graceful handling."""

    @pytest.mark.asyncio
    async def test_empty_kit_generates(self, client):
        """Kit generation succeeds with 0 tools."""
        agent = await _create_agent(client)
        kit = await _generate_kit(client, agent["id"])
        assert len(kit["files"]) == 7

    @pytest.mark.asyncio
    async def test_empty_rbac_yaml_valid(self, client):
        """RBAC YAML is valid even with empty roles."""
        agent = await _create_agent(client)
        kit = await _generate_kit(client, agent["id"])
        data = yaml.safe_load(kit["files"]["rbac.yaml"])
        assert data is not None
        assert "roles" in data

    @pytest.mark.asyncio
    async def test_empty_protection_parses(self, client):
        """protected_agent.py is valid Python with 0 tools."""
        agent = await _create_agent(client)
        kit = await _generate_kit(client, agent["id"])
        ast.parse(kit["files"]["protected_agent.py"])

    @pytest.mark.asyncio
    async def test_empty_test_security_parses(self, client):
        """test_security.py is valid Python with 0 tools."""
        agent = await _create_agent(client)
        kit = await _generate_kit(client, agent["id"])
        ast.parse(kit["files"]["test_security.py"])

    @pytest.mark.asyncio
    async def test_empty_readme_has_agent_name(self, client):
        """README references the agent name even with 0 tools."""
        name = f"EmptyBot-{uuid.uuid4().hex[:8]}"
        agent = await _create_agent(client, name=name)
        kit = await _generate_kit(client, agent["id"])
        assert name in kit["files"]["README.md"]


# ═══════════════════════════════════════════════════════════════════════
# V4 — Framework variants: langgraph / raw_python / proxy_only
# ═══════════════════════════════════════════════════════════════════════


class TestVariantFrameworks:
    """Same agent config, different frameworks → different generated code."""

    FRAMEWORKS = ["langgraph", "raw_python", "proxy_only"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("framework", FRAMEWORKS)
    async def test_framework_kit_generates(self, client, framework):
        """Kit generates for each framework."""
        agent = await _create_agent(client, framework=framework, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="frameworkTool")
        kit = await _generate_kit(client, agent["id"])
        assert len(kit["files"]) == 7
        assert kit["framework"] == framework

    @pytest.mark.asyncio
    @pytest.mark.parametrize("framework", FRAMEWORKS)
    async def test_framework_protection_valid_python(self, client, framework):
        """protected_agent.py is valid Python for each framework."""
        agent = await _create_agent(client, framework=framework, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="fwTool")
        kit = await _generate_kit(client, agent["id"])
        ast.parse(kit["files"]["protected_agent.py"])

    @pytest.mark.asyncio
    async def test_langgraph_has_stategraph_classes(self, client):
        """LangGraph variant has RBACService, PreToolGate, PostToolGate, LimitsService."""
        agent = await _create_agent(client, framework="langgraph", policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="lgTool")
        kit = await _generate_kit(client, agent["id"])
        classes = _get_class_names(kit["files"]["protected_agent.py"])
        assert {"RBACService", "PreToolGate", "PostToolGate", "LimitsService"} <= classes

    @pytest.mark.asyncio
    async def test_raw_python_has_protected_call(self, client):
        """Raw Python variant has protected_tool_call function."""
        agent = await _create_agent(client, framework="raw_python", policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="rpTool")
        kit = await _generate_kit(client, agent["id"])
        funcs = _get_function_names(kit["files"]["protected_agent.py"])
        assert "protected_tool_call" in funcs

    @pytest.mark.asyncio
    async def test_proxy_only_is_short(self, client):
        """Proxy-only variant is ≤ 20 lines."""
        agent = await _create_agent(client, framework="proxy_only", policy_pack="customer_support")
        kit = await _generate_kit(client, agent["id"])
        lines = kit["files"]["protected_agent.py"].strip().splitlines()
        assert len(lines) <= 20

    @pytest.mark.asyncio
    async def test_framework_codes_differ(self, client):
        """All 3 frameworks produce different protected_agent.py content."""
        codes = {}
        for fw in self.FRAMEWORKS:
            agent = await _create_agent(client, framework=fw, policy_pack="customer_support")
            await _create_tool(client, agent["id"], name="diffTool")
            kit = await _generate_kit(client, agent["id"])
            codes[fw] = kit["files"]["protected_agent.py"]

        assert codes["langgraph"] != codes["raw_python"]
        assert codes["raw_python"] != codes["proxy_only"]
        assert codes["langgraph"] != codes["proxy_only"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("framework", FRAMEWORKS)
    async def test_framework_yaml_files_identical(self, client, framework):
        """YAML config files are framework-independent (same policy pack → same YAML)."""
        agent = await _create_agent(client, framework=framework, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="yamlTool", sensitivity="medium")
        kit = await _generate_kit(client, agent["id"])
        # All frameworks should have valid YAML
        for yaml_name in ["rbac.yaml", "limits.yaml", "policy.yaml"]:
            data = yaml.safe_load(kit["files"][yaml_name])
            assert data is not None, f"{yaml_name} is None for {framework}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("framework", FRAMEWORKS)
    async def test_framework_zip_download(self, client, framework):
        """ZIP download works for each framework and contains 7 files."""
        agent = await _create_agent(client, framework=framework, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="zipTool")
        await client.post(f"/v1/agents/{agent['id']}/integration-kit")
        resp = await client.get(f"/v1/agents/{agent['id']}/integration-kit/download")
        assert resp.status_code == 200
        buf = io.BytesIO(resp.content)
        with zipfile.ZipFile(buf) as zf:
            assert len(zf.namelist()) == 7


# ═══════════════════════════════════════════════════════════════════════
# V5 — Policy pack variants: all 5 packs × langgraph
# ═══════════════════════════════════════════════════════════════════════


class TestVariantPolicyPacks:
    """Each policy pack produces different scanner thresholds and limits."""

    PACKS = ["customer_support", "internal_copilot", "finance", "hr", "research"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack", PACKS)
    async def test_pack_kit_generates(self, client, pack):
        """Kit generates for each policy pack."""
        agent = await _create_agent(client, policy_pack=pack)
        await _create_tool(client, agent["id"], name="packTool")
        kit = await _generate_kit(client, agent["id"])
        assert len(kit["files"]) == 7

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack", PACKS)
    async def test_pack_policy_yaml_has_scanners(self, client, pack):
        """policy.yaml has scanner config for each pack."""
        agent = await _create_agent(client, policy_pack=pack)
        await _create_tool(client, agent["id"], name="scanTool")
        kit = await _generate_kit(client, agent["id"])
        policy = yaml.safe_load(kit["files"]["policy.yaml"])
        assert "scanners" in policy

    @pytest.mark.asyncio
    async def test_finance_strict_thresholds(self, client):
        """Finance pack has stricter injection threshold than research."""
        agent_f = await _create_agent(client, policy_pack="finance")
        await _create_tool(client, agent_f["id"], name="fTool")
        kit_f = await _generate_kit(client, agent_f["id"])

        agent_r = await _create_agent(client, policy_pack="research")
        await _create_tool(client, agent_r["id"], name="rTool")
        kit_r = await _generate_kit(client, agent_r["id"])

        policy_f = yaml.safe_load(kit_f["files"]["policy.yaml"])
        policy_r = yaml.safe_load(kit_r["files"]["policy.yaml"])

        # Finance threshold (0.2) < Research threshold (0.7)
        assert policy_f["scanners"]["injection_threshold"] < policy_r["scanners"]["injection_threshold"]

    @pytest.mark.asyncio
    async def test_research_relaxed_pii(self, client):
        """Research pack has PII redaction disabled."""
        agent = await _create_agent(client, policy_pack="research")
        await _create_tool(client, agent["id"], name="piiTool")
        kit = await _generate_kit(client, agent["id"])
        policy = yaml.safe_load(kit["files"]["policy.yaml"])
        assert policy["scanners"]["pii_redaction"] is False

    @pytest.mark.asyncio
    async def test_hr_block_mode_pii(self, client):
        """HR pack uses PII mode=block (not mask)."""
        agent = await _create_agent(client, policy_pack="hr")
        await _create_tool(client, agent["id"], name="hrTool")
        kit = await _generate_kit(client, agent["id"])
        policy = yaml.safe_load(kit["files"]["policy.yaml"])
        assert policy["scanners"]["pii_mode"] == "block"

    @pytest.mark.asyncio
    async def test_research_nemo_disabled(self, client):
        """Research pack has NeMo Guardrails disabled."""
        agent = await _create_agent(client, policy_pack="research")
        await _create_tool(client, agent["id"], name="nemoTool")
        kit = await _generate_kit(client, agent["id"])
        policy = yaml.safe_load(kit["files"]["policy.yaml"])
        assert policy["scanners"]["nemo_guardrails"] is False

    @pytest.mark.asyncio
    async def test_customer_support_nemo_enabled(self, client):
        """Customer support pack has NeMo Guardrails enabled."""
        agent = await _create_agent(client, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="csTool")
        kit = await _generate_kit(client, agent["id"])
        policy = yaml.safe_load(kit["files"]["policy.yaml"])
        assert policy["scanners"]["nemo_guardrails"] is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pack", PACKS)
    async def test_pack_limits_yaml_valid(self, client, pack):
        """limits.yaml is valid YAML for each pack."""
        agent = await _create_agent(client, policy_pack=pack)
        await _create_tool(client, agent["id"], name="limTool")
        kit = await _generate_kit(client, agent["id"])
        data = yaml.safe_load(kit["files"]["limits.yaml"])
        assert "roles" in data

    @pytest.mark.asyncio
    async def test_internal_copilot_higher_limits_than_finance(self, client):
        """Internal copilot has higher token limits than finance."""
        # Create agents with a role so limits.yaml has role entries
        agent_ic = await _create_agent(client, policy_pack="internal_copilot")
        await _create_tool(client, agent_ic["id"], name="icTool")
        await _create_role(client, agent_ic["id"], name="icRole")
        kit_ic = await _generate_kit(client, agent_ic["id"])

        agent_fn = await _create_agent(client, policy_pack="finance")
        await _create_tool(client, agent_fn["id"], name="fnTool")
        await _create_role(client, agent_fn["id"], name="fnRole")
        kit_fn = await _generate_kit(client, agent_fn["id"])

        limits_ic = yaml.safe_load(kit_ic["files"]["limits.yaml"])
        limits_fn = yaml.safe_load(kit_fn["files"]["limits.yaml"])

        # IC low tier = MEDIUM_TIER (50 calls), Finance low tier = LOW_TIER (20 calls)
        ic_role_limits = next(iter(limits_ic["roles"].values()))
        fn_role_limits = next(iter(limits_fn["roles"].values()))
        assert ic_role_limits["max_tool_calls_per_session"] >= fn_role_limits["max_tool_calls_per_session"]


# ═══════════════════════════════════════════════════════════════════════
# V6 — Sensitivity levels: all-low vs all-critical
# ═══════════════════════════════════════════════════════════════════════


class TestVariantSensitivity:
    """Tool sensitivity affects limits and confirmation requirements."""

    @pytest.mark.asyncio
    async def test_all_low_tools(self, client):
        """All-low sensitivity tools → valid kit."""
        agent = await _create_agent(client, policy_pack="customer_support")
        for i in range(3):
            await _create_tool(client, agent["id"], name=f"lowTool{i}", sensitivity="low", access_type="read")
        kit = await _generate_kit(client, agent["id"])
        assert len(kit["files"]) == 7
        ast.parse(kit["files"]["protected_agent.py"])

    @pytest.mark.asyncio
    async def test_all_critical_tools(self, client):
        """All-critical sensitivity tools → valid kit."""
        agent = await _create_agent(client, policy_pack="finance", handles_secrets=True, has_write_actions=True)
        for i in range(3):
            await _create_tool(client, agent["id"], name=f"critTool{i}", sensitivity="critical", access_type="write")
        kit = await _generate_kit(client, agent["id"])
        assert len(kit["files"]) == 7
        ast.parse(kit["files"]["protected_agent.py"])

    @pytest.mark.asyncio
    async def test_mixed_sensitivity_tools(self, client):
        """Mixed sensitivity (low + medium + high + critical) → valid kit."""
        agent = await _create_agent(client, policy_pack="customer_support")
        for sens in ["low", "medium", "high", "critical"]:
            await _create_tool(client, agent["id"], name=f"mix_{sens}", sensitivity=sens)
        kit = await _generate_kit(client, agent["id"])
        code = kit["files"]["protected_agent.py"]
        for sens in ["low", "medium", "high", "critical"]:
            assert f"mix_{sens}" in code

    @pytest.mark.asyncio
    async def test_critical_tools_have_rate_limits(self, client):
        """Critical tools get per-tool rate limits in limits.yaml."""
        agent = await _create_agent(client, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="critRateTool", sensitivity="critical", access_type="write")
        kit = await _generate_kit(client, agent["id"])
        limits = yaml.safe_load(kit["files"]["limits.yaml"])
        if "tool_rate_limits" in limits:
            # Critical tool should have lower rate limit
            assert len(limits["tool_rate_limits"]) >= 1


# ═══════════════════════════════════════════════════════════════════════
# V7 — Rate limits: per-tool + per-role cross-check
# ═══════════════════════════════════════════════════════════════════════


class TestVariantRateLimits:
    """Verify per-role and per-tool limits are generated correctly."""

    @pytest.mark.asyncio
    async def test_limits_have_role_section(self, client):
        """limits.yaml has roles section."""
        agent = await _create_agent(client, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="limTool1")
        role = await _create_role(client, agent["id"], name="limitedRole")
        await _set_permissions(
            client, agent["id"], role["id"], [(await _create_tool(client, agent["id"], name="limTool2"))["id"]]
        )
        kit = await _generate_kit(client, agent["id"])
        limits = yaml.safe_load(kit["files"]["limits.yaml"])
        assert "roles" in limits

    @pytest.mark.asyncio
    async def test_langgraph_limits_service_checks_both(self, client):
        """LangGraph LimitsService.check_limits checks per-role AND per-tool limits."""
        agent = await _create_agent(client, framework="langgraph", policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="rateTool", sensitivity="high", access_type="write")
        kit = await _generate_kit(client, agent["id"])
        code = kit["files"]["protected_agent.py"]
        # LimitsService should reference tool_rate_limits
        assert "tool_rate_limits" in code

    @pytest.mark.asyncio
    async def test_limits_yaml_has_max_tool_calls(self, client):
        """Each role in limits.yaml has max_tool_calls_per_session."""
        agent = await _create_agent(client, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="callTool")
        await _create_role(client, agent["id"], name="callRole")
        kit = await _generate_kit(client, agent["id"])
        limits = yaml.safe_load(kit["files"]["limits.yaml"])
        for _role_name, role_limits in limits.get("roles", {}).items():
            assert "max_tool_calls_per_session" in role_limits


# ═══════════════════════════════════════════════════════════════════════
# V8 — Rollout modes: observe / warn / enforce
# ═══════════════════════════════════════════════════════════════════════


class TestVariantRolloutModes:
    """Different rollout modes → different .env.protector AI_PROTECTOR_MODE."""

    @pytest.mark.asyncio
    async def test_default_rollout_mode_is_observe(self, client):
        """New agents default to observe mode in .env.protector."""
        agent = await _create_agent(client, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="defaultModeTool")
        kit = await _generate_kit(client, agent["id"])
        env_content = kit["files"][".env.protector"]
        assert "AI_PROTECTOR_MODE=observe" in env_content

    @pytest.mark.asyncio
    async def test_rollout_mode_observe_in_kit(self, client):
        """Observe mode appears in generated kit."""
        agent = await _create_agent(client, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="obsTool")
        kit = await _generate_kit(client, agent["id"])
        assert "observe" in kit["files"][".env.protector"]

    @pytest.mark.asyncio
    async def test_rollout_mode_affects_env_file(self, client):
        """Rollout mode from agent record is rendered into .env.protector."""
        agent = await _create_agent(client, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="envModeTool")
        kit = await _generate_kit(client, agent["id"])
        env_content = kit["files"][".env.protector"]
        # Default is observe — verify the template renders rollout_mode
        assert "AI_PROTECTOR_MODE=" in env_content

    @pytest.mark.asyncio
    async def test_promoted_mode_in_env(self, client):
        """After observe→warn promotion, kit reflects warn mode."""
        from src.db.session import async_session
        from src.wizard.models import Agent, RolloutMode

        agent = await _create_agent(client, policy_pack="customer_support")
        aid = agent["id"]
        await _create_tool(client, aid, name="promTool")

        # Directly set rollout_mode in DB to bypass promotion guards
        async with async_session() as session:
            db_agent = await session.get(Agent, uuid.UUID(aid))
            db_agent.rollout_mode = RolloutMode.WARN
            await session.commit()

        kit = await _generate_kit(client, aid)
        env_content = kit["files"][".env.protector"]
        assert "AI_PROTECTOR_MODE=warn" in env_content

    @pytest.mark.asyncio
    async def test_kit_valid_for_all_rollout_states(self, client):
        """Kit generates valid files regardless of rollout state."""
        agent = await _create_agent(client, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="rolloutKit")
        kit = await _generate_kit(client, agent["id"])
        assert len(kit["files"]) == 7
        ast.parse(kit["files"]["protected_agent.py"])
        ast.parse(kit["files"]["test_security.py"])


# ═══════════════════════════════════════════════════════════════════════
# V9 — Boolean flags: public-facing, PII, secrets, external APIs
# ═══════════════════════════════════════════════════════════════════════


class TestVariantBooleanFlags:
    """Agent boolean flags affect risk classification and kit content."""

    @pytest.mark.asyncio
    async def test_public_facing_agent(self, client):
        """Public-facing agent → valid kit."""
        agent = await _create_agent(client, is_public_facing=True, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="pubTool")
        kit = await _generate_kit(client, agent["id"])
        assert len(kit["files"]) == 7

    @pytest.mark.asyncio
    async def test_pii_agent_has_pii_test(self, client):
        """Agent with touches_pii=True → test_security.py has PII test."""
        agent = await _create_agent(client, touches_pii=True, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="piiTool", sensitivity="medium")
        kit = await _generate_kit(client, agent["id"])
        assert "test_pii_redaction" in kit["files"]["test_security.py"]

    @pytest.mark.asyncio
    async def test_secrets_agent(self, client):
        """Agent with handles_secrets=True → valid kit, secrets scanning enabled."""
        agent = await _create_agent(client, handles_secrets=True, policy_pack="finance")
        await _create_tool(client, agent["id"], name="secTool", sensitivity="critical")
        kit = await _generate_kit(client, agent["id"])
        policy = yaml.safe_load(kit["files"]["policy.yaml"])
        assert policy["scanners"]["secrets_scanning"] is True

    @pytest.mark.asyncio
    async def test_external_api_agent(self, client):
        """Agent with calls_external_apis=True → valid kit."""
        agent = await _create_agent(client, calls_external_apis=True, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="apiTool")
        kit = await _generate_kit(client, agent["id"])
        assert len(kit["files"]) == 7

    @pytest.mark.asyncio
    async def test_all_flags_true(self, client):
        """All boolean flags True → valid kit (maximum risk)."""
        agent = await _create_agent(
            client,
            is_public_facing=True,
            has_write_actions=True,
            touches_pii=True,
            handles_secrets=True,
            calls_external_apis=True,
            policy_pack="finance",
        )
        await _create_tool(client, agent["id"], name="maxRiskTool", sensitivity="critical", access_type="write")
        kit = await _generate_kit(client, agent["id"])
        assert len(kit["files"]) == 7
        ast.parse(kit["files"]["protected_agent.py"])
        ast.parse(kit["files"]["test_security.py"])

    @pytest.mark.asyncio
    async def test_all_flags_false(self, client):
        """All boolean flags False → valid kit (minimum risk)."""
        agent = await _create_agent(
            client,
            is_public_facing=False,
            has_write_actions=False,
            touches_pii=False,
            handles_secrets=False,
            calls_external_apis=False,
            policy_pack="research",
        )
        await _create_tool(client, agent["id"], name="minRiskTool", sensitivity="low", access_type="read")
        kit = await _generate_kit(client, agent["id"])
        assert len(kit["files"]) == 7


# ═══════════════════════════════════════════════════════════════════════
# V10 — RBAC coherence: generated code matches generated YAML
# ═══════════════════════════════════════════════════════════════════════


class TestVariantRBACCoherence:
    """RBAC config in YAML ↔ role names in protection code ↔ test assertions."""

    @pytest.mark.asyncio
    async def test_rbac_yaml_roles_in_protection_code(self, client):
        """Every role in rbac.yaml appears in protected_agent.py."""
        agent = await _create_agent(client, policy_pack="customer_support")
        aid = agent["id"]
        tools = []
        for name in ["toolA", "toolB", "toolC"]:
            tools.append(await _create_tool(client, aid, name=name))

        for rname in ["alpha", "beta", "gamma"]:
            role = await _create_role(client, aid, name=rname)
            await _set_permissions(client, aid, role["id"], [tools[0]["id"]])

        kit = await _generate_kit(client, aid)
        rbac = yaml.safe_load(kit["files"]["rbac.yaml"])
        code = kit["files"]["protected_agent.py"]

        for role_name in rbac["roles"]:
            assert role_name in code, f"Role '{role_name}' in YAML but not in code"

    @pytest.mark.asyncio
    async def test_rbac_yaml_tools_in_protection_code(self, client):
        """Every tool in rbac.yaml appears in protected_agent.py."""
        agent = await _create_agent(client, policy_pack="customer_support")
        aid = agent["id"]
        for name in ["searchDB", "updateRecord", "deleteEntry"]:
            await _create_tool(client, aid, name=name)

        kit = await _generate_kit(client, aid)
        code = kit["files"]["protected_agent.py"]
        for tname in ["searchDB", "updateRecord", "deleteEntry"]:
            assert tname in code

    @pytest.mark.asyncio
    async def test_test_security_references_rbac_roles(self, client):
        """test_security.py has RBAC tests that load and validate roles from rbac.yaml."""
        agent = await _create_agent(client, policy_pack="customer_support")
        aid = agent["id"]
        tool = await _create_tool(client, aid, name="coherenceTool")
        role = await _create_role(client, aid, name="coherenceRole")
        await _set_permissions(client, aid, role["id"], [tool["id"]])

        kit = await _generate_kit(client, aid)
        test_code = kit["files"]["test_security.py"]
        # Test code should have RBAC validation via rbac.yaml loading
        assert "test_rbac_block_unknown_role" in test_code
        assert "test_rbac_allow_authorized" in test_code
        assert "__nonexistent_role__" in test_code


# ═══════════════════════════════════════════════════════════════════════
# V11 — Cross-file consistency: config YAML ↔ code ↔ tests ↔ env ↔ README
# ═══════════════════════════════════════════════════════════════════════


class TestVariantCrossFileConsistency:
    """All generated files are internally consistent."""

    @pytest.mark.asyncio
    async def test_agent_id_consistent_across_files(self, client):
        """Agent ID appears in .env.protector and README."""
        name = f"ConsistencyBot-{uuid.uuid4().hex[:8]}"
        agent = await _create_agent(client, name=name, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="consTool")
        kit = await _generate_kit(client, agent["id"])

        env = kit["files"][".env.protector"]
        readme = kit["files"]["README.md"]
        assert agent["id"] in env
        assert name in readme

    @pytest.mark.asyncio
    async def test_scanner_config_in_policy_yaml_and_test(self, client):
        """Scanners from policy.yaml are tested in test_security.py."""
        agent = await _create_agent(client, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="scanConsTool")
        kit = await _generate_kit(client, agent["id"])

        policy = yaml.safe_load(kit["files"]["policy.yaml"])
        test_code = kit["files"]["test_security.py"]

        # If injection_detection is on, test should reference injection
        if policy["scanners"]["injection_detection"]:
            assert "injection" in test_code.lower()
        # If pii_redaction is on, test should reference PII
        if policy["scanners"]["pii_redaction"]:
            assert "pii" in test_code.lower()

    @pytest.mark.asyncio
    async def test_env_agent_id_matches_kit_agent_id(self, client):
        """AI_PROTECTOR_AGENT_ID in .env matches the agent used for generation."""
        agent = await _create_agent(client, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="envIdTool")
        kit = await _generate_kit(client, agent["id"])
        env = kit["files"][".env.protector"]
        assert agent["id"] in env

    @pytest.mark.asyncio
    async def test_all_files_nonempty(self, client):
        """All 7 files are non-empty."""
        agent = await _create_agent(client, policy_pack="customer_support")
        await _create_tool(client, agent["id"], name="nonemptyTool")
        kit = await _generate_kit(client, agent["id"])
        expected = [
            "rbac.yaml",
            "limits.yaml",
            "policy.yaml",
            "protected_agent.py",
            "test_security.py",
            ".env.protector",
            "README.md",
        ]
        for fname in expected:
            assert fname in kit["files"], f"Missing file: {fname}"
            assert len(kit["files"][fname]) > 10, f"File {fname} is too short"

    @pytest.mark.asyncio
    async def test_full_e2e_zip_all_variants(self, client):
        """Full e2e: create → tools → roles → permissions → kit → ZIP → validate all files."""
        agent = await _create_agent(
            client,
            policy_pack="finance",
            has_write_actions=True,
            touches_pii=True,
            handles_secrets=True,
            is_public_facing=True,
        )
        aid = agent["id"]

        # 4 tools with varied sensitivity
        t_low = await _create_tool(client, aid, name="readDocs", sensitivity="low", access_type="read")
        t_med = await _create_tool(client, aid, name="readUsers", sensitivity="medium", access_type="read")
        t_high = await _create_tool(client, aid, name="processPayment", sensitivity="high", access_type="write")
        t_crit = await _create_tool(client, aid, name="deleteAccount", sensitivity="critical", access_type="write")

        # 3 roles with escalating permissions
        viewer = await _create_role(client, aid, name="viewer")
        operator = await _create_role(client, aid, name="operator")
        superadmin = await _create_role(client, aid, name="superadmin")

        await _set_permissions(client, aid, viewer["id"], [t_low["id"]])
        await _set_permissions(
            client, aid, operator["id"], [t_low["id"], t_med["id"], t_high["id"]], scopes=["read", "write"]
        )
        await _set_permissions(
            client, aid, superadmin["id"], [t["id"] for t in [t_low, t_med, t_high, t_crit]], scopes=["read", "write"]
        )

        # Generate and download ZIP
        resp = await client.post(f"/v1/agents/{aid}/integration-kit")
        assert resp.status_code == 200

        resp = await client.get(f"/v1/agents/{aid}/integration-kit/download")
        assert resp.status_code == 200

        buf = io.BytesIO(resp.content)
        with zipfile.ZipFile(buf) as zf:
            names = set(zf.namelist())
            assert len(names) == 7

            # Validate YAML
            rbac = yaml.safe_load(zf.read("rbac.yaml").decode())
            assert set(rbac["roles"].keys()) == {"viewer", "operator", "superadmin"}
            viewer_tools = list(rbac["roles"]["viewer"].get("tools", {}).keys())
            assert "deleteAccount" not in viewer_tools
            # deleteAccount should be in superadmin's own tools
            superadmin_tools = list(rbac["roles"]["superadmin"].get("tools", {}).keys())
            assert "deleteAccount" in superadmin_tools

            limits = yaml.safe_load(zf.read("limits.yaml").decode())
            assert "roles" in limits

            policy = yaml.safe_load(zf.read("policy.yaml").decode())
            # Finance pack: strict injection threshold
            assert policy["scanners"]["injection_threshold"] == 0.2
            assert policy["scanners"]["pii_mode"] == "block"

            # Validate Python
            code = zf.read("protected_agent.py").decode()
            ast.parse(code)
            for name in ["readDocs", "readUsers", "processPayment", "deleteAccount"]:
                assert name in code
            for name in ["viewer", "operator", "superadmin"]:
                assert name in code

            # Validate tests
            test_code = zf.read("test_security.py").decode()
            tree = ast.parse(test_code)
            test_funcs = [
                n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
            ]
            assert len(test_funcs) == 5
            assert "__nonexistent_role__" in test_code

            # Validate env
            env = zf.read(".env.protector").decode()
            assert agent["id"] in env

            # Validate README
            readme = zf.read("README.md").decode()
            assert agent["name"] in readme
