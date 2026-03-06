"""Shared test fixtures for agent-demo."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Default to "real" mode in tests so mocked acompletion paths are exercised.
os.environ.setdefault("MODE", "real")

from src.config import get_settings  # noqa: E402

get_settings.cache_clear()

from src.main import app  # noqa: E402


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)
