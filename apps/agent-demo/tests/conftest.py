"""Shared test fixtures for agent-demo."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Force "real" mode in tests — agent tests mock acompletion directly
# and must not go through demo's mock_agent_llm path.
os.environ["MODE"] = "real"

from src.config import get_settings  # noqa: E402

get_settings.cache_clear()

from src.main import app  # noqa: E402


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)
