"""Shared test fixtures for agent-demo."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)
