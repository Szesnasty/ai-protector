"""SSRF egress guard — validate_url must fail closed on internal targets by default."""

from __future__ import annotations

import pytest

from src.red_team import net

# IP literals so resolution is deterministic and offline (getaddrinfo returns them directly).
_INTERNAL = [
    "http://169.254.169.254/latest/meta-data/",  # cloud metadata (link-local)
    "http://127.0.0.1:8000/",  # loopback
    "http://10.0.0.5/",  # RFC1918 private
    "http://192.168.1.1/",  # RFC1918 private
]


@pytest.fixture
def _default_egress(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force default-secure egress regardless of the suite-wide opt-in."""
    monkeypatch.delenv("RED_TEAM_ALLOW_PRIVATE_TARGETS", raising=False)


@pytest.mark.parametrize("url", _INTERNAL)
def test_blocks_internal_targets_by_default(_default_egress: None, url: str) -> None:
    assert net.validate_url(url) is None


def test_allows_public_target_by_default(_default_egress: None) -> None:
    # 8.8.8.8 is a public IP literal — not loopback/private/link-local/reserved.
    assert net.validate_url("http://8.8.8.8/") is not None


def test_rejects_non_http_scheme(_default_egress: None) -> None:
    assert net.validate_url("file:///etc/passwd") is None
    assert net.validate_url("gopher://127.0.0.1/") is None


def test_rejects_missing_host(_default_egress: None) -> None:
    assert net.validate_url("http:///no-host") is None


def test_opt_in_allows_private_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RED_TEAM_ALLOW_PRIVATE_TARGETS", "true")
    assert net.validate_url("http://127.0.0.1:8000/") is not None
    assert net.validate_url("http://10.0.0.5/") is not None
