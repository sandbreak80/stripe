"""Tests for admin API endpoints."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from fastapi.testclient import TestClient

from billing_service.main import app
from billing_service.models import ManualGrant
from billing_service.database import get_db
from billing_service.auth import verify_admin_api_key


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def admin_headers():
    """Admin API headers."""
    return {"Authorization": "Bearer admin_key_123"}


@patch("billing_service.config.settings")
def test_create_grant_success(mock_settings, client, db_session, test_project):
    """Test successful grant creation."""
    mock_settings.admin_api_key = "admin_key_123"
    
    # Use FastAPI dependency override
    async def override_get_db():
        yield db_session
    
    async def override_verify_admin():
        return "admin_user"
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_admin_api_key] = override_verify_admin
    
    try:
        response = client.post(
            "/api/v1/admin/grant",
            headers={"Authorization": "Bearer admin_key_123"},
            json={
                "user_id": "user_123",
                "project_id": "test-project",
                "feature_code": "premium_feature",
                "reason": "Test grant",
            },
        )
        
        # Should succeed with proper mocking
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


@patch("billing_service.config.settings")
def test_revoke_grant_success(mock_settings, client, db_session, test_project):
    """Test successful grant revocation."""
    mock_settings.admin_api_key = "admin_key_123"
    
    # Create grant first
    grant = ManualGrant(
        user_id="user_123",
        project_id=test_project.id,
        feature_code="premium_feature",
        valid_from=datetime.utcnow(),
        reason="Test grant",
        granted_by="admin_user",
    )
    db_session.add(grant)
    db_session.commit()
    
    # Use FastAPI dependency override
    async def override_get_db():
        yield db_session
    
    async def override_verify_admin():
        return "admin_user"
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_admin_api_key] = override_verify_admin
    
    try:
        response = client.post(
            "/api/v1/admin/revoke",
            headers={"Authorization": "Bearer admin_key_123"},
            json={
                "grant_id": str(grant.id),
                "revoke_reason": "Test revocation",
            },
        )
        
        # Should succeed with proper mocking
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


@patch("billing_service.config.settings")
@patch("billing_service.admin.reconcile_all")
def test_trigger_reconciliation(mock_reconcile, mock_settings, client):
    """Test reconciliation trigger."""
    mock_settings.admin_api_key = "admin_key_123"
    mock_reconcile.return_value = Mock(errors=[], subscriptions_updated=0, purchases_updated=0)
    
    # Use FastAPI dependency override
    async def override_verify_admin():
        return "admin_user"
    
    app.dependency_overrides[verify_admin_api_key] = override_verify_admin
    
    try:
        response = client.post(
            "/api/v1/admin/reconcile",
            headers={"Authorization": "Bearer admin_key_123"},
        )
        
        # Should succeed with proper mocking
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
