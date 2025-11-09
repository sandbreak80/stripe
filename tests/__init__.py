"""Test configuration and fixtures."""

import pytest
from fastapi.testclient import TestClient

from billing_service.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)
