"""Tests for P2-03 Auth Secret Handling.

Covers: encryption roundtrip, DB storage, API stripping, TTL cleanup,
HTTP client integration, SecretStore interface.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.red_team.secrets.encryption import decrypt, encrypt
from src.red_team.secrets.store import EncryptedColumnSecretStore, SecretStore, is_encrypted_ref

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TEST_KEY = "a" * 64  # 32 bytes of 0xaa


@pytest.fixture(autouse=True)
def _set_secret_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BENCHMARK_SECRET_KEY", _TEST_KEY)


# ---------------------------------------------------------------------------
# Encryption tests
# ---------------------------------------------------------------------------


def test_encrypt_decrypt_roundtrip():
    """encrypt -> decrypt returns original plaintext."""
    secret = "Bearer sk-super-secret-key-12345"
    ciphertext = encrypt(secret)
    assert ciphertext != secret
    assert decrypt(ciphertext) == secret


def test_encrypt_produces_different_ciphertexts():
    """Each call to encrypt uses a random nonce -> different ciphertext."""
    secret = "Bearer abc"
    ct1 = encrypt(secret)
    ct2 = encrypt(secret)
    assert ct1 != ct2
    # Both decrypt to same value
    assert decrypt(ct1) == secret
    assert decrypt(ct2) == secret


def test_decrypt_invalid_token():
    """Decrypting garbage raises an exception."""
    with pytest.raises(Exception):
        decrypt("not-valid-base64-ciphertext!!!")


def test_missing_key(monkeypatch: pytest.MonkeyPatch):
    """encrypt raises RuntimeError when key env var is missing."""
    monkeypatch.delenv("BENCHMARK_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="not set"):
        encrypt("secret")


# ---------------------------------------------------------------------------
# SecretStore tests
# ---------------------------------------------------------------------------


async def test_secret_store_interface():
    """EncryptedColumnSecretStore implements SecretStore protocol."""
    assert isinstance(EncryptedColumnSecretStore(), SecretStore)


async def test_encrypted_column_store_roundtrip():
    """store -> retrieve returns original value."""
    store = EncryptedColumnSecretStore()
    ref = await store.store("auth", "Bearer token-123", ttl_hours=24)
    assert is_encrypted_ref(ref)
    assert ref.startswith("encrypted:")
    result = await store.retrieve(ref)
    assert result == "Bearer token-123"


async def test_encrypted_column_store_retrieve_invalid():
    """retrieve returns None for non-encrypted ref."""
    store = EncryptedColumnSecretStore()
    assert await store.retrieve("not-encrypted") is None


# ---------------------------------------------------------------------------
# Service-level integration: encrypted stored in DB
# ---------------------------------------------------------------------------


async def test_encrypted_stored_in_db():
    """When auth_header is in target_config, service encrypts it."""
    from src.red_team.api.service import BenchmarkService

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)
    mock_session.execute = AsyncMock(return_value=type("R", (), {"scalar_one_or_none": lambda self: None})())

    svc = BenchmarkService(mock_session)

    with (
        patch.object(svc._run_repo, "find_running_for_target", return_value=None),
        patch.object(svc._run_repo, "create", side_effect=lambda run: run),
    ):
        run = await svc.create_run(
            target_type="hosted_endpoint",
            target_config={
                "endpoint_url": "https://api.example.com/chat",
                "auth_header": "Bearer sk-secret-123",
            },
            pack="core_security",
        )

    # auth_header should be gone, auth_secret_ref should be present
    assert "auth_header" not in run.target_config
    assert "auth_secret_ref" in run.target_config
    ref = run.target_config["auth_secret_ref"]
    assert ref.startswith("encrypted:")

    # Verify we can decrypt it
    store = EncryptedColumnSecretStore()
    plaintext = await store.retrieve(ref)
    assert plaintext == "Bearer sk-secret-123"


# ---------------------------------------------------------------------------
# API response stripping
# ---------------------------------------------------------------------------


async def test_auth_stripped_from_api_response():
    """get_run_safe masks auth_secret_ref in target_config."""
    from src.red_team.api.service import BenchmarkService
    from src.red_team.persistence.models import BenchmarkRun

    fake_run = BenchmarkRun(
        id=uuid.uuid4(),
        target_type="hosted_endpoint",
        target_config={"endpoint_url": "https://x.com", "auth_secret_ref": "encrypted:abcdef"},
        target_fingerprint="abc123",
        pack="core_security",
        status="completed",
    )

    mock_session = AsyncMock(spec=AsyncSession)
    svc = BenchmarkService(mock_session)

    with patch.object(svc._run_repo, "get", return_value=fake_run):
        result = await svc.get_run_safe(fake_run.id)

    assert result is not None
    assert result.target_config["auth_secret_ref"] == "***"


# ---------------------------------------------------------------------------
# Plaintext never in logs (verify strip_auth_from_config)
# ---------------------------------------------------------------------------


def test_plaintext_never_in_logs():
    """strip_auth_from_config replaces auth_secret_ref with ***."""
    from src.red_team.api.service import strip_auth_from_config

    config = {
        "endpoint_url": "https://api.example.com",
        "auth_secret_ref": "encrypted:very-long-ciphertext-here",
    }
    safe = strip_auth_from_config(config)
    assert safe["auth_secret_ref"] == "***"
    assert safe["endpoint_url"] == "https://api.example.com"
    # Original not mutated
    assert config["auth_secret_ref"] != "***"


# ---------------------------------------------------------------------------
# TTL auto-deletion
# ---------------------------------------------------------------------------


async def test_auth_deleted_after_ttl():
    """cleanup_expired_secrets nulls out auth_secret_ref after 24h."""
    from src.red_team.api.service import cleanup_expired_secrets
    from src.red_team.persistence.models import BenchmarkRun

    old_run = BenchmarkRun(
        id=uuid.uuid4(),
        target_type="hosted_endpoint",
        target_config={"endpoint_url": "https://x.com", "auth_secret_ref": "encrypted:abc"},
        target_fingerprint="abc",
        pack="core_security",
        status="completed",
        completed_at=datetime.now(UTC) - timedelta(hours=25),
    )

    # Mock session that returns old_run (expired) from the cleanup query
    mock_session = AsyncMock(spec=AsyncSession)
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [old_run]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    cleaned = await cleanup_expired_secrets(mock_session)
    assert cleaned == 1
    assert "auth_secret_ref" not in old_run.target_config


# ---------------------------------------------------------------------------
# HTTP client receives decrypted auth
# ---------------------------------------------------------------------------


async def test_http_client_receives_decrypted():
    """decrypt_auth_for_run returns decrypted plaintext for run engine."""
    from src.red_team.api.service import BenchmarkService
    from src.red_team.persistence.models import BenchmarkRun

    # Encrypt a known value
    secret = "Bearer sk-for-http-client"
    store = EncryptedColumnSecretStore()
    ref = await store.store("auth", secret, ttl_hours=24)

    fake_run = BenchmarkRun(
        id=uuid.uuid4(),
        target_type="hosted_endpoint",
        target_config={"endpoint_url": "https://x.com", "auth_secret_ref": ref},
        target_fingerprint="abc",
        pack="core_security",
        status="running",
    )

    mock_session = AsyncMock(spec=AsyncSession)
    svc = BenchmarkService(mock_session)
    decrypted = await svc.decrypt_auth_for_run(fake_run)
    assert decrypted == secret


# ---------------------------------------------------------------------------
# Auth stripped from export (target_config in JSON)
# ---------------------------------------------------------------------------


def test_auth_stripped_from_export():
    """Export JSON should not contain auth_secret_ref."""
    from src.red_team.api.service import strip_auth_from_config

    config = {
        "endpoint_url": "https://api.example.com",
        "auth_secret_ref": "encrypted:secret-data",
        "timeout_s": 30,
    }
    export_config = strip_auth_from_config(config)
    # In a real export this dict would be serialized to JSON
    import json

    export_json = json.dumps(export_config)
    assert "encrypted:" not in export_json
    assert "secret-data" not in export_json
    assert "***" in export_json
