"""Tests for CRUD operations on /v1/policies/{policy_id}/rules endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def client():
    """Async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _get_balanced_policy_id(client: AsyncClient) -> str:
    """Return the ID of the 'balanced' policy."""
    resp = await client.get("/v1/policies")
    policies = resp.json()
    balanced = next(p for p in policies if p["name"] == "balanced")
    return balanced["id"]


async def _create_rule(client: AsyncClient, policy_id: str, **overrides) -> dict:
    """Create a test rule and return the response JSON."""
    body = {
        "phrase": f"test-phrase-{uuid.uuid4().hex[:8]}",
        "category": "general",
        "action": "block",
        "severity": "medium",
        "description": "Test rule",
        **overrides,
    }
    resp = await client.post(f"/v1/policies/{policy_id}/rules", json=body)
    assert resp.status_code == 201
    return resp.json()


# ── LIST ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_rules_returns_seed_data(client: AsyncClient):
    """GET /v1/policies/{id}/rules should return seed rules with new fields."""
    pid = await _get_balanced_policy_id(client)
    resp = await client.get(f"/v1/policies/{pid}/rules")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 10  # 18 seed rules

    # Verify new fields exist on seed rules
    first = data[0]
    assert "action" in first
    assert "severity" in first
    assert "description" in first
    assert first["action"] in ("block", "flag", "score_boost")
    assert first["severity"] in ("low", "medium", "high", "critical")


@pytest.mark.asyncio
async def test_list_rules_filter_by_category(client: AsyncClient):
    """Filter rules by category prefix."""
    pid = await _get_balanced_policy_id(client)
    resp = await client.get(f"/v1/policies/{pid}/rules", params={"category": "intent:"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(r["category"].startswith("intent:") for r in data)


@pytest.mark.asyncio
async def test_list_rules_filter_by_action(client: AsyncClient):
    """Filter rules by action."""
    pid = await _get_balanced_policy_id(client)
    resp = await client.get(f"/v1/policies/{pid}/rules", params={"action": "flag"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(r["action"] == "flag" for r in data)


@pytest.mark.asyncio
async def test_list_rules_search(client: AsyncClient):
    """Search rules by phrase or description."""
    pid = await _get_balanced_policy_id(client)
    resp = await client.get(f"/v1/policies/{pid}/rules", params={"search": "DAN"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_list_rules_404_missing_policy(client: AsyncClient):
    """Listing rules for a non-existent policy returns 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/v1/policies/{fake_id}/rules")
    assert resp.status_code == 404


# ── CREATE ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_rule(client: AsyncClient):
    """POST a new rule and verify response."""
    pid = await _get_balanced_policy_id(client)
    body = {
        "phrase": "hack the system",
        "category": "intent:jailbreak",
        "action": "block",
        "severity": "critical",
        "description": "Custom: hack keyword",
    }
    resp = await client.post(f"/v1/policies/{pid}/rules", json=body)
    assert resp.status_code == 201
    data = resp.json()
    assert data["phrase"] == "hack the system"
    assert data["category"] == "intent:jailbreak"
    assert data["action"] == "block"
    assert data["severity"] == "critical"
    assert data["description"] == "Custom: hack keyword"
    assert data["policy_id"] == pid
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_rule_invalid_regex(client: AsyncClient):
    """Creating a rule with invalid regex returns 422."""
    pid = await _get_balanced_policy_id(client)
    body = {
        "phrase": "[invalid(regex",
        "is_regex": True,
        "category": "general",
    }
    resp = await client.post(f"/v1/policies/{pid}/rules", json=body)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_rule_defaults(client: AsyncClient):
    """Creating a rule with minimal fields uses defaults."""
    pid = await _get_balanced_policy_id(client)
    body = {"phrase": "test default fields"}
    resp = await client.post(f"/v1/policies/{pid}/rules", json=body)
    assert resp.status_code == 201
    data = resp.json()
    assert data["action"] == "block"
    assert data["severity"] == "medium"
    assert data["category"] == "general"
    assert data["description"] == ""
    assert data["is_regex"] is False


# ── UPDATE ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_rule(client: AsyncClient):
    """PATCH a rule and verify changes."""
    pid = await _get_balanced_policy_id(client)
    rule = await _create_rule(client, pid)

    resp = await client.patch(
        f"/v1/policies/{pid}/rules/{rule['id']}",
        json={"severity": "high", "description": "Updated description"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["severity"] == "high"
    assert data["description"] == "Updated description"
    # Other fields unchanged
    assert data["phrase"] == rule["phrase"]


@pytest.mark.asyncio
async def test_update_rule_not_found(client: AsyncClient):
    """Updating a non-existent rule returns 404."""
    pid = await _get_balanced_policy_id(client)
    fake_id = str(uuid.uuid4())
    resp = await client.patch(
        f"/v1/policies/{pid}/rules/{fake_id}",
        json={"severity": "low"},
    )
    assert resp.status_code == 404


# ── DELETE ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_rule(client: AsyncClient):
    """DELETE a rule returns 204."""
    pid = await _get_balanced_policy_id(client)
    rule = await _create_rule(client, pid)

    resp = await client.delete(f"/v1/policies/{pid}/rules/{rule['id']}")
    assert resp.status_code == 204

    # Verify it's gone
    resp2 = await client.get(f"/v1/policies/{pid}/rules")
    ids = {r["id"] for r in resp2.json()}
    assert rule["id"] not in ids


@pytest.mark.asyncio
async def test_delete_rule_not_found(client: AsyncClient):
    """Deleting a non-existent rule returns 404."""
    pid = await _get_balanced_policy_id(client)
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/v1/policies/{pid}/rules/{fake_id}")
    assert resp.status_code == 404


# ── BULK IMPORT ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_import(client: AsyncClient):
    """Bulk import creates rules and skips duplicates."""
    pid = await _get_balanced_policy_id(client)
    rules = [
        {"phrase": f"bulk-{uuid.uuid4().hex[:6]}", "category": "general", "action": "block", "severity": "high"},
        {"phrase": f"bulk-{uuid.uuid4().hex[:6]}", "category": "general", "action": "flag", "severity": "low"},
    ]
    resp = await client.post(
        f"/v1/policies/{pid}/rules/import",
        json={"rules": rules},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["created"] == 2
    assert data["skipped"] == 0

    # Import again — should skip
    resp2 = await client.post(
        f"/v1/policies/{pid}/rules/import",
        json={"rules": rules},
    )
    data2 = resp2.json()
    assert data2["created"] == 0
    assert data2["skipped"] == 2


# ── TEST ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rule_test_endpoint(client: AsyncClient):
    """Test rules against sample text."""
    pid = await _get_balanced_policy_id(client)

    # Create a simple rule
    await _create_rule(client, pid, phrase="evil plan", is_regex=False, action="block")

    resp = await client.post(
        f"/v1/policies/{pid}/rules/test",
        json={"text": "I have an evil plan to hack"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(r["phrase"] == "evil plan" and r["matched"] for r in data)


@pytest.mark.asyncio
async def test_rule_test_regex(client: AsyncClient):
    """Test regex rules return match details."""
    pid = await _get_balanced_policy_id(client)

    await _create_rule(
        client, pid,
        phrase=r"(?i)\bhack\b",
        is_regex=True,
        action="block",
        severity="critical",
    )

    resp = await client.post(
        f"/v1/policies/{pid}/rules/test",
        json={"text": "I will hack the system"},
    )
    assert resp.status_code == 200
    data = resp.json()
    regex_match = [r for r in data if r["phrase"] == r"(?i)\bhack\b"]
    assert len(regex_match) >= 1
    assert regex_match[0]["matched"] is True
    assert regex_match[0]["match_details"] is not None


# ── EXPORT ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_rules(client: AsyncClient):
    """Export returns all rules as JSON array."""
    pid = await _get_balanced_policy_id(client)
    resp = await client.get(f"/v1/policies/{pid}/rules/export")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 10  # seed rules
    # Verify all fields present
    for rule in data:
        assert "id" in rule
        assert "phrase" in rule
        assert "action" in rule
        assert "severity" in rule
        assert "description" in rule
