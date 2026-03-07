"""Tests for /v1/rules — additional coverage for edge cases and sync logic."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _create_rule(client: AsyncClient, **overrides) -> dict:
    body = {
        "phrase": f"cov-{uuid.uuid4().hex[:8]}",
        "category": "general",
        "action": "block",
        "severity": "medium",
        "description": "Coverage test rule",
        **overrides,
    }
    resp = await client.post("/v1/rules", json=body)
    assert resp.status_code == 201
    return resp.json()


# ── UPDATE edge-cases ────────────────────────────────────────────────


class TestUpdateEdgeCases:
    """Cover update paths not exercised by existing tests."""

    @pytest.mark.asyncio
    async def test_update_noop(self, client: AsyncClient):
        """PATCH with empty body returns rule unchanged."""
        rule = await _create_rule(client)
        resp = await client.patch(f"/v1/rules/{rule['id']}", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["phrase"] == rule["phrase"]
        assert data["severity"] == rule["severity"]

    @pytest.mark.asyncio
    async def test_update_phrase_and_category(self, client: AsyncClient):
        """PATCH can change phrase and category together."""
        rule = await _create_rule(client)
        resp = await client.patch(
            f"/v1/rules/{rule['id']}",
            json={"phrase": "updated-phrase", "category": "intent:test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["phrase"] == "updated-phrase"
        assert data["category"] == "intent:test"

    @pytest.mark.asyncio
    async def test_update_to_regex(self, client: AsyncClient):
        """PATCH can switch a plain rule to regex."""
        rule = await _create_rule(client, is_regex=False)
        resp = await client.patch(
            f"/v1/rules/{rule['id']}",
            json={"phrase": r"(?i)test\d+", "is_regex": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_regex"] is True
        assert data["phrase"] == r"(?i)test\d+"

    @pytest.mark.asyncio
    async def test_update_invalid_regex(self, client: AsyncClient):
        """PATCH with invalid regex returns 422."""
        rule = await _create_rule(client)
        resp = await client.patch(
            f"/v1/rules/{rule['id']}",
            json={"phrase": "[bad(regex", "is_regex": True},
        )
        assert resp.status_code == 422
        assert "Invalid regex" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_action_and_severity(self, client: AsyncClient):
        """PATCH can change action and severity."""
        rule = await _create_rule(client, action="block", severity="low")
        resp = await client.patch(
            f"/v1/rules/{rule['id']}",
            json={"action": "flag", "severity": "critical"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "flag"
        assert data["severity"] == "critical"


# ── BULK IMPORT edge-cases ───────────────────────────────────────────


class TestBulkImportEdgeCases:
    """Cover bulk import edge cases."""

    @pytest.mark.asyncio
    async def test_bulk_import_invalid_regex_skipped(self, client: AsyncClient):
        """Invalid regex rules are skipped during bulk import."""
        rules = [
            {
                "phrase": "[invalid(regex",
                "is_regex": True,
                "category": "general",
                "action": "block",
                "severity": "high",
            },
            {
                "phrase": f"valid-{uuid.uuid4().hex[:6]}",
                "category": "general",
                "action": "block",
                "severity": "medium",
            },
        ]
        resp = await client.post("/v1/rules/import", json={"rules": rules})
        assert resp.status_code == 201
        data = resp.json()
        assert data["created"] == 1
        assert data["skipped"] == 1

    @pytest.mark.asyncio
    async def test_bulk_import_empty_list(self, client: AsyncClient):
        """Bulk import with empty rules list is rejected (422)."""
        resp = await client.post("/v1/rules/import", json={"rules": []})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_bulk_import_with_valid_regex(self, client: AsyncClient):
        """Bulk import with valid regex creates rule."""
        rules = [
            {
                "phrase": rf"(?i)\bbulk-test-{uuid.uuid4().hex[:6]}\b",
                "is_regex": True,
                "category": "general",
                "action": "block",
                "severity": "high",
            },
        ]
        resp = await client.post("/v1/rules/import", json={"rules": rules})
        assert resp.status_code == 201
        data = resp.json()
        assert data["created"] == 1


# ── CREATE edge-cases ────────────────────────────────────────────────


class TestCreateEdgeCases:
    """Cover create paths."""

    @pytest.mark.asyncio
    async def test_create_regex_rule(self, client: AsyncClient):
        """Creating a valid regex rule succeeds."""
        body = {
            "phrase": r"(?i)ignore\s+all",
            "is_regex": True,
            "category": "intent:jailbreak",
            "action": "block",
            "severity": "critical",
            "description": "Regex test",
        }
        resp = await client.post("/v1/rules", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["is_regex"] is True

    @pytest.mark.asyncio
    async def test_create_flag_action(self, client: AsyncClient):
        """Rules with action='flag' are created correctly."""
        rule = await _create_rule(client, action="flag", severity="low")
        assert rule["action"] == "flag"
        assert rule["severity"] == "low"

    @pytest.mark.asyncio
    async def test_create_score_boost_action(self, client: AsyncClient):
        """Rules with action='score_boost' are created correctly."""
        rule = await _create_rule(client, action="score_boost", severity="high")
        assert rule["action"] == "score_boost"


# ── TEST endpoint edge-cases ─────────────────────────────────────────


class TestRuleTestEndpoint:
    """Cover rule test edge cases."""

    @pytest.mark.asyncio
    async def test_no_matches(self, client: AsyncClient):
        """Testing totally benign text returns empty or no matches from custom rules."""
        resp = await client.post(
            "/v1/rules/test",
            json={"text": "Hello, how are you today?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_case_insensitive_match(self, client: AsyncClient):
        """Plain phrase matching is case-insensitive."""
        phrase = f"casematch-{uuid.uuid4().hex[:6]}"
        await _create_rule(client, phrase=phrase)

        resp = await client.post(
            "/v1/rules/test",
            json={"text": f"I said {phrase.upper()} loudly"},
        )
        assert resp.status_code == 200
        data = resp.json()
        matches = [r for r in data if r["phrase"] == phrase]
        assert len(matches) == 1
        assert matches[0]["matched"] is True


# ── DELETE + verify sync ─────────────────────────────────────────────


class TestDeleteSync:
    """Verify delete syncs across policies."""

    @pytest.mark.asyncio
    async def test_delete_then_export_confirms_removal(self, client: AsyncClient):
        """Rule removed from export after deletion."""
        rule = await _create_rule(client, phrase=f"del-sync-{uuid.uuid4().hex[:8]}")
        resp = await client.delete(f"/v1/rules/{rule['id']}")
        assert resp.status_code == 204

        export = await client.get("/v1/rules/export")
        phrases = {r["phrase"] for r in export.json()}
        assert rule["phrase"] not in phrases
