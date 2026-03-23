"""Tests for src.config — Settings parsing and version fallback."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.config import Settings, _get_package_version

# ── Version fallback ──────────────────────────────────────────────────


class TestGetPackageVersion:
    """_get_package_version() behaviour."""

    def test_returns_installed_version(self) -> None:
        """When the package is installed, return its metadata version."""
        ver = _get_package_version()
        # Installed in editable mode → real version from pyproject.toml
        assert ver != "0.0.0-unknown"
        assert ver.count(".") >= 2  # semver-ish

    def test_fallback_when_package_not_installed(self) -> None:
        """When importlib.metadata cannot find the package, return fallback."""
        with patch(
            "importlib.metadata.version",
            side_effect=Exception("not found"),
        ):
            assert _get_package_version() == "0.0.0-unknown"


# ── json_logs ─────────────────────────────────────────────────────────


class TestJsonLogs:
    """json_logs parsed from environment."""

    def test_default_is_false(self) -> None:
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.json_logs is False

    @pytest.mark.parametrize("value", ["true", "True", "1", "yes"])
    def test_truthy_env_values(self, value: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JSON_LOGS", value)
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.json_logs is True

    @pytest.mark.parametrize("value", ["false", "False", "0", "no"])
    def test_falsy_env_values(self, value: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JSON_LOGS", value)
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.json_logs is False


# ── cors_origins ──────────────────────────────────────────────────────


class TestCorsOrigins:
    """cors_origins accepts JSON array and comma-separated string."""

    def test_default_origins(self) -> None:
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.cors_origins == [
            "http://localhost:3000",
            "http://frontend:3000",
        ]

    def test_json_encoded_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            "CORS_ORIGINS",
            '["https://app.example.com","https://admin.example.com"]',
        )
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.cors_origins == [
            "https://app.example.com",
            "https://admin.example.com",
        ]

    def test_comma_separated_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            "CORS_ORIGINS",
            "https://app.example.com, https://admin.example.com",
        )
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.cors_origins == [
            "https://app.example.com",
            "https://admin.example.com",
        ]

    def test_single_origin_no_comma(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CORS_ORIGINS", "https://only.example.com")
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.cors_origins == ["https://only.example.com"]
