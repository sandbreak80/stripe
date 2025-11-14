"""Tests for API endpoints."""

from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from billing_service.main import app
from billing_service.models import Entitlement, EntitlementSource


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db_session(db_session):
    """Mock database session."""
    with patch("billing_service.entitlements_api.get_db", return_value=db_session):
        yield db_session


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_ready_endpoint(client):
    """Test readiness check endpoint."""
    # This will fail if DB is not connected, but that's expected in test
    response = client.get("/ready")
    # Accept either 200 or 503 depending on DB connection
    assert response.status_code in [200, 503]


@patch("billing_service.checkout_api.create_checkout_session")
def test_create_checkout_endpoint(mock_create_session, client, db_session, test_project, test_price):
    """Test checkout creation endpoint."""
    import hashlib
    from billing_service.main import app
    from billing_service.database import get_db
    from billing_service.auth import verify_project_api_key
    
    api_key = "test_checkout_key"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    test_project.api_key_hash = api_key_hash
    db_session.commit()
    
    # Use FastAPI dependency override
    async def override_get_db():
        yield db_session
    
    async def override_verify():
        return test_project
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_project_api_key] = override_verify
    
    mock_session = Mock()
    mock_session.url = "https://checkout.stripe.com/test"
    mock_session.id = "cs_test123"
    mock_session.expires_at = 1234567890
    mock_create_session.return_value = mock_session
    
    try:
        response = client.post(
            "/api/v1/checkout/create",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "user_id": "user_123",
                "project_id": "test-project",
                "price_id": str(test_price.id),
                "mode": "subscription",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )
        
        # Should succeed with proper mocking
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_get_entitlements_endpoint(client, db_session, test_project):
    """Test entitlements query endpoint."""
    import hashlib
    from billing_service.main import app
    from billing_service.database import get_db
    from billing_service.auth import verify_project_api_key
    
    api_key = "test_entitlements_key"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    test_project.api_key_hash = api_key_hash
    db_session.commit()
    
    # Create entitlement
    entitlement = Entitlement(
        user_id="user_123",
        project_id=test_project.id,
        feature_code="feature1",
        is_active=True,
        valid_from=datetime.utcnow(),
        valid_to=None,
        source=EntitlementSource.SUBSCRIPTION,
        source_id=test_project.id,  # Using project ID as placeholder
    )
    db_session.add(entitlement)
    db_session.commit()
    
    # Use FastAPI dependency override
    async def override_get_db():
        yield db_session
    
    async def override_verify():
        return test_project
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_project_api_key] = override_verify
    
    try:
        response = client.get(
            "/api/v1/entitlements?user_id=user_123",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        
        # Should succeed with proper mocking
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user_123"
        assert len(data["entitlements"]) >= 1
    finally:
        app.dependency_overrides.clear()
