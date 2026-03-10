"""Tests for Agent CRUD — spec 26 (35 tests).

Covers:
  26a — DB model (6 tests)
  26b — Risk classification (12 tests)
  26c — CRUD API (13 tests)
  26d — Seed (4 tests)
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.wizard.models import (
    Agent,
    ProtectionLevel,
    RiskLevel,
)
from src.wizard.schemas import AgentCreate, AgentUpdate
from src.wizard.seed import seed_reference_agent
from src.wizard.services.risk import compute_risk_level, recommend_protection_level


@pytest.fixture
async def client():
    """Async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Helpers ──────────────────────────────────────────────────────────────

_AGENT_BODY = {
    "name": "Test Agent",
    "description": "A test agent for unit tests",
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


async def _create_agent(client: AsyncClient, **overrides) -> dict:
    """POST a test agent and return response JSON."""
    body = {**_AGENT_BODY, **overrides}
    resp = await client.post("/v1/agents", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _make_agent(**kwargs) -> Agent:
    """Create an in-memory Agent ORM instance for risk tests."""
    defaults = {
        "name": "risk-test",
        "is_public_facing": False,
        "has_tools": True,
        "has_write_actions": False,
        "touches_pii": False,
        "handles_secrets": False,
        "calls_external_apis": False,
    }
    defaults.update(kwargs)
    return Agent(**defaults)


# ═══════════════════════════════════════════════════════════════════════
# 26a — DB model (6 tests)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_agent_model(client: AsyncClient):
    """Agent row inserted, id is UUID, created_at auto-set."""
    data = await _create_agent(client, name=f"model-{uuid.uuid4().hex[:8]}")
    assert uuid.UUID(data["id"])
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


@pytest.mark.asyncio
async def test_agent_default_values(client: AsyncClient):
    """New agent has status=draft, rollout_mode=observe."""
    data = await _create_agent(client, name=f"defaults-{uuid.uuid4().hex[:8]}")
    assert data["status"] == "draft"
    assert data["rollout_mode"] == "observe"


@pytest.mark.asyncio
async def test_agent_framework_enum(client: AsyncClient):
    """Only langgraph/raw_python/proxy_only accepted."""
    resp = await client.post("/v1/agents", json={**_AGENT_BODY, "name": "enum-fw", "framework": "invalid"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_agent_environment_enum(client: AsyncClient):
    """Only dev/staging/production accepted."""
    resp = await client.post("/v1/agents", json={**_AGENT_BODY, "name": "enum-env", "environment": "invalid"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_migration_creates_table(client: AsyncClient):
    """Table exists — we can list agents without error."""
    resp = await client.get("/v1/agents")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_pydantic_schemas_validation():
    """AgentCreate rejects missing name; AgentUpdate allows partial."""
    with pytest.raises(Exception):
        AgentCreate()  # type: ignore[call-arg] — name required

    # AgentUpdate allows all-None (empty partial update)
    update = AgentUpdate()
    assert update.name is None


# ═══════════════════════════════════════════════════════════════════════
# 26b — Risk classification (12 tests)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_risk_low():
    """!write && !pii && !secrets && !public → LOW."""
    agent = _make_agent()
    assert compute_risk_level(agent) == RiskLevel.LOW


@pytest.mark.asyncio
async def test_risk_medium_write():
    """write && !pii && !public → MEDIUM."""
    agent = _make_agent(has_write_actions=True)
    assert compute_risk_level(agent) == RiskLevel.MEDIUM


@pytest.mark.asyncio
async def test_risk_medium_public_tools():
    """public && tools && !write → MEDIUM."""
    agent = _make_agent(is_public_facing=True, has_tools=True)
    assert compute_risk_level(agent) == RiskLevel.MEDIUM


@pytest.mark.asyncio
async def test_risk_high_write_public():
    """write && public → HIGH."""
    agent = _make_agent(has_write_actions=True, is_public_facing=True)
    assert compute_risk_level(agent) == RiskLevel.HIGH


@pytest.mark.asyncio
async def test_risk_high_pii():
    """pii=true → HIGH."""
    agent = _make_agent(touches_pii=True)
    assert compute_risk_level(agent) == RiskLevel.HIGH


@pytest.mark.asyncio
async def test_risk_high_secrets():
    """secrets=true → HIGH."""
    agent = _make_agent(handles_secrets=True)
    assert compute_risk_level(agent) == RiskLevel.HIGH


@pytest.mark.asyncio
async def test_risk_critical():
    """write && pii && public → CRITICAL."""
    agent = _make_agent(has_write_actions=True, touches_pii=True, is_public_facing=True)
    assert compute_risk_level(agent) == RiskLevel.CRITICAL


@pytest.mark.asyncio
async def test_risk_all_false():
    """All capabilities false → LOW."""
    agent = _make_agent(
        has_write_actions=False,
        touches_pii=False,
        handles_secrets=False,
        is_public_facing=False,
        has_tools=False,
    )
    assert compute_risk_level(agent) == RiskLevel.LOW


@pytest.mark.asyncio
async def test_risk_all_true():
    """All capabilities true → CRITICAL."""
    agent = _make_agent(
        has_write_actions=True,
        touches_pii=True,
        handles_secrets=True,
        is_public_facing=True,
        has_tools=True,
        calls_external_apis=True,
    )
    assert compute_risk_level(agent) == RiskLevel.CRITICAL


@pytest.mark.asyncio
async def test_protection_level_low():
    """risk LOW → proxy_only."""
    assert recommend_protection_level(RiskLevel.LOW) == ProtectionLevel.PROXY_ONLY


@pytest.mark.asyncio
async def test_protection_level_medium():
    """risk MEDIUM → agent_runtime."""
    assert recommend_protection_level(RiskLevel.MEDIUM) == ProtectionLevel.AGENT_RUNTIME


@pytest.mark.asyncio
async def test_protection_level_high_critical():
    """risk HIGH/CRITICAL → full."""
    assert recommend_protection_level(RiskLevel.HIGH) == ProtectionLevel.FULL
    assert recommend_protection_level(RiskLevel.CRITICAL) == ProtectionLevel.FULL


# ═══════════════════════════════════════════════════════════════════════
# 26c — CRUD API (13 tests)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_post_creates_agent(client: AsyncClient):
    """POST /v1/agents → 201, body has id + computed risk."""
    data = await _create_agent(client, name=f"create-{uuid.uuid4().hex[:8]}")
    assert "id" in data
    assert data["risk_level"] is not None
    assert data["protection_level"] is not None


@pytest.mark.asyncio
async def test_post_missing_name(client: AsyncClient):
    """POST without name → 422."""
    body = {k: v for k, v in _AGENT_BODY.items() if k != "name"}
    resp = await client.post("/v1/agents", json=body)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_name_too_short(client: AsyncClient):
    """POST name='a' → 422."""
    resp = await client.post("/v1/agents", json={**_AGENT_BODY, "name": "a"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_duplicate_name(client: AsyncClient):
    """POST same name twice → 409."""
    name = f"dup-{uuid.uuid4().hex[:8]}"
    await _create_agent(client, name=name)
    resp = await client.post("/v1/agents", json={**_AGENT_BODY, "name": name})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_list_returns_items(client: AsyncClient):
    """GET /v1/agents returns paginated list."""
    await _create_agent(client, name=f"list-{uuid.uuid4().hex[:8]}")
    resp = await client.get("/v1/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_list_pagination(client: AsyncClient):
    """Pagination works with per_page and page."""
    # Create enough agents
    for i in range(3):
        await _create_agent(client, name=f"page-{uuid.uuid4().hex[:8]}-{i}")

    resp = await client.get("/v1/agents", params={"per_page": 2, "page": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) <= 2
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_get_list_filter_status(client: AsyncClient):
    """GET ?status=active → only active agents."""
    resp = await client.get("/v1/agents", params={"status": "active"})
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["status"] == "active"


@pytest.mark.asyncio
async def test_get_list_filter_risk(client: AsyncClient):
    """GET ?risk_level=low → only low-risk agents."""
    await _create_agent(client, name=f"risk-filter-{uuid.uuid4().hex[:8]}")
    resp = await client.get("/v1/agents", params={"risk_level": "low"})
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["risk_level"] == "low"


@pytest.mark.asyncio
async def test_get_list_filter_team(client: AsyncClient):
    """GET ?team=platform → only platform team agents."""
    await _create_agent(client, name=f"team-filter-{uuid.uuid4().hex[:8]}", team="platform")
    resp = await client.get("/v1/agents", params={"team": "platform"})
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["team"] == "platform"


@pytest.mark.asyncio
async def test_get_detail(client: AsyncClient):
    """GET /v1/agents/:id → 200, full agent object."""
    created = await _create_agent(client, name=f"detail-{uuid.uuid4().hex[:8]}")
    resp = await client.get(f"/v1/agents/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == created["name"]


@pytest.mark.asyncio
async def test_get_detail_not_found(client: AsyncClient):
    """GET /v1/agents/nonexistent → 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/v1/agents/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_updates_and_recomputes_risk(client: AsyncClient):
    """PATCH touches_pii=true → risk re-computed to HIGH."""
    created = await _create_agent(client, name=f"patch-{uuid.uuid4().hex[:8]}")
    assert created["risk_level"] == "low"

    resp = await client.patch(f"/v1/agents/{created['id']}", json={"touches_pii": True})
    assert resp.status_code == 200
    assert resp.json()["risk_level"] == "high"
    assert resp.json()["protection_level"] == "full"


@pytest.mark.asyncio
async def test_delete_soft_deletes(client: AsyncClient):
    """DELETE → status=archived, not in active list."""
    created = await _create_agent(client, name=f"del-{uuid.uuid4().hex[:8]}")
    agent_id = created["id"]

    resp = await client.delete(f"/v1/agents/{agent_id}")
    assert resp.status_code == 204

    # Detail still accessible
    resp = await client.get(f"/v1/agents/{agent_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"

    # Not in default list (excludes archived)
    resp = await client.get("/v1/agents")
    ids = [a["id"] for a in resp.json()["items"]]
    assert agent_id not in ids


# ═══════════════════════════════════════════════════════════════════════
# 26d — Seed (4 tests)
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_seed_creates_reference_agent(client: AsyncClient):
    """After seed, 'Customer Support Copilot' exists."""
    await seed_reference_agent()
    resp = await client.get("/v1/agents", params={"status": "active"})
    names = [a["name"] for a in resp.json()["items"]]
    assert "Customer Support Copilot" in names


@pytest.mark.asyncio
async def test_reference_agent_non_deletable(client: AsyncClient):
    """DELETE reference agent → 403."""
    await seed_reference_agent()
    resp = await client.get("/v1/agents", params={"status": "active"})
    ref = next(a for a in resp.json()["items"] if a["is_reference"])
    resp = await client.delete(f"/v1/agents/{ref['id']}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reference_agent_top_of_list(client: AsyncClient):
    """GET /v1/agents → reference agent is first."""
    await seed_reference_agent()
    # Create a regular agent so there's more than one
    await _create_agent(client, name=f"after-ref-{uuid.uuid4().hex[:8]}", status="active")
    resp = await client.get("/v1/agents", params={"status": "active"})
    items = resp.json()["items"]
    ref_items = [a for a in items if a["is_reference"]]
    if ref_items:
        assert items[0]["is_reference"] is True


@pytest.mark.asyncio
async def test_seed_idempotent(client: AsyncClient):
    """Run seed twice → still 1 reference agent."""
    await seed_reference_agent()
    await seed_reference_agent()
    resp = await client.get("/v1/agents", params={"status": "active"})
    ref_count = sum(1 for a in resp.json()["items"] if a["is_reference"])
    assert ref_count == 1
