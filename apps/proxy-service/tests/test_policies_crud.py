"""Tests for CRUD operations on /v1/policies endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def client():
    """Async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Helpers ──────────────────────────────────────────────────────────────

_CUSTOM_POLICY = {
    "name": "test-custom",
    "description": "A test policy",
    "config": {"nodes": [], "thresholds": {"max_risk": 0.8}},
    "is_active": True,
}


async def _create_custom_policy(client: AsyncClient, **overrides) -> dict:
    """POST a custom policy and return the response JSON."""
    body = {**_CUSTOM_POLICY, **overrides}
    resp = await client.post("/v1/policies", json=body)
    assert resp.status_code == 201
    return resp.json()


async def _cleanup_policy(client: AsyncClient, policy_id: str) -> None:
    """Hard-cleanup: use PATCH to deactivate (soft-delete won't work for builtins)."""
    # Just ignore errors — best effort
    await client.patch(
        f"/v1/policies/{policy_id}",
        json={"is_active": False},
    )


# ── GET /v1/policies ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_policies_returns_seeded(client: AsyncClient):
    """GET /v1/policies should return at least the 4 built-in policies."""
    resp = await client.get("/v1/policies")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    names = {p["name"] for p in data}
    assert {"fast", "balanced", "strict", "paranoid"} <= names


@pytest.mark.asyncio
async def test_list_policies_active_only_default(client: AsyncClient):
    """Default active_only=true should exclude inactive policies."""
    # Create + deactivate a custom policy
    created = await _create_custom_policy(client, name=f"inactive-{uuid.uuid4().hex[:8]}")
    pid = created["id"]
    await client.delete(f"/v1/policies/{pid}")

    resp = await client.get("/v1/policies")
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()}
    assert pid not in ids


@pytest.mark.asyncio
async def test_list_policies_include_inactive(client: AsyncClient):
    """active_only=false should include deactivated policies."""
    created = await _create_custom_policy(client, name=f"inactive2-{uuid.uuid4().hex[:8]}")
    pid = created["id"]
    await client.delete(f"/v1/policies/{pid}")

    resp = await client.get("/v1/policies", params={"active_only": "false"})
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()}
    assert pid in ids


# ── GET /v1/policies/{id} ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_policy_by_id(client: AsyncClient):
    """GET /v1/policies/{id} should return the policy."""
    # Get a policy from list first
    resp = await client.get("/v1/policies")
    policies = resp.json()
    first = policies[0]

    resp = await client.get(f"/v1/policies/{first['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == first["id"]
    assert data["name"] == first["name"]
    assert "config" in data
    assert "version" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_get_policy_not_found(client: AsyncClient):
    """GET /v1/policies/{id} with unknown UUID should return 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/v1/policies/{fake_id}")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ── POST /v1/policies ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_policy(client: AsyncClient):
    """POST /v1/policies should create and return 201."""
    name = f"new-policy-{uuid.uuid4().hex[:8]}"
    body = {
        "name": name,
        "description": "Testing create",
        "config": {"nodes": ["llm_guard"], "thresholds": {"max_risk": 0.6}},
    }
    resp = await client.post("/v1/policies", json=body)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == name
    assert data["description"] == "Testing create"
    assert data["config"]["thresholds"]["max_risk"] == 0.6
    assert data["version"] == 1
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_policy_duplicate_name(client: AsyncClient):
    """POST /v1/policies with duplicate name should return 409."""
    resp = await client.post("/v1/policies", json={
        "name": "balanced",
        "description": "duplicate",
        "config": {},
    })
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


# ── PATCH /v1/policies/{id} ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_policy_description(client: AsyncClient):
    """PATCH /v1/policies/{id} should update fields and bump version."""
    created = await _create_custom_policy(client, name=f"upd-{uuid.uuid4().hex[:8]}")
    pid = created["id"]
    original_version = created["version"]

    resp = await client.patch(
        f"/v1/policies/{pid}",
        json={"description": "Updated description"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["description"] == "Updated description"
    assert data["version"] == original_version + 1


@pytest.mark.asyncio
async def test_update_policy_config(client: AsyncClient):
    """PATCH config should replace it and bump version."""
    created = await _create_custom_policy(client, name=f"cfg-{uuid.uuid4().hex[:8]}")
    pid = created["id"]

    new_config = {"nodes": ["presidio"], "thresholds": {"max_risk": 0.3}}
    resp = await client.patch(f"/v1/policies/{pid}", json={"config": new_config})
    assert resp.status_code == 200
    data = resp.json()
    assert data["config"] == new_config


@pytest.mark.asyncio
async def test_update_policy_not_found(client: AsyncClient):
    """PATCH with unknown UUID should return 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.patch(f"/v1/policies/{fake_id}", json={"description": "x"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_empty_body_no_version_bump(client: AsyncClient):
    """PATCH with empty body should not bump version."""
    created = await _create_custom_policy(client, name=f"empty-{uuid.uuid4().hex[:8]}")
    pid = created["id"]
    original_version = created["version"]

    resp = await client.patch(f"/v1/policies/{pid}", json={})
    assert resp.status_code == 200
    assert resp.json()["version"] == original_version


# ── DELETE /v1/policies/{id} ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_custom_policy(client: AsyncClient):
    """DELETE should soft-delete (set is_active=False) and return 204."""
    created = await _create_custom_policy(client, name=f"del-{uuid.uuid4().hex[:8]}")
    pid = created["id"]

    resp = await client.delete(f"/v1/policies/{pid}")
    assert resp.status_code == 204

    # Verify it's now inactive
    resp = await client.get(f"/v1/policies/{pid}")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_builtin_policy_forbidden(client: AsyncClient):
    """DELETE on built-in policy should return 403."""
    # Get the 'balanced' policy ID
    resp = await client.get("/v1/policies")
    balanced = next(p for p in resp.json() if p["name"] == "balanced")

    resp = await client.delete(f"/v1/policies/{balanced['id']}")
    assert resp.status_code == 403
    assert "built-in" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_not_found(client: AsyncClient):
    """DELETE with unknown UUID should return 404."""
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/v1/policies/{fake_id}")
    assert resp.status_code == 404


# ── Redis cache invalidation ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_invalidates_redis_cache(client: AsyncClient):
    """PATCH should invalidate Redis cache for the policy."""
    created = await _create_custom_policy(client, name=f"redis-{uuid.uuid4().hex[:8]}")
    pid = created["id"]

    with patch("src.routers.policies.get_redis", new_callable=AsyncMock) as mock_redis:
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client

        resp = await client.patch(
            f"/v1/policies/{pid}",
            json={"description": "trigger cache invalidation"},
        )
        assert resp.status_code == 200
        mock_redis_client.delete.assert_called_once_with(
            f"policy_config:{created['name']}"
        )


@pytest.mark.asyncio
async def test_delete_invalidates_redis_cache(client: AsyncClient):
    """DELETE should invalidate Redis cache for the policy."""
    created = await _create_custom_policy(client, name=f"rdel-{uuid.uuid4().hex[:8]}")
    pid = created["id"]

    with patch("src.routers.policies.get_redis", new_callable=AsyncMock) as mock_redis:
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client

        resp = await client.delete(f"/v1/policies/{pid}")
        assert resp.status_code == 204
        mock_redis_client.delete.assert_called_once_with(
            f"policy_config:{created['name']}"
        )
