"""Tests for admin API endpoints."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import httpx

from billing_service.main import app
from billing_service.models import ManualGrant
from billing_service.database import get_db
from billing_service.auth import verify_admin_api_key


@pytest.fixture
def admin_headers():
    """Admin API headers."""
    return {"Authorization": "Bearer admin_key_123"}


@pytest.mark.asyncio
async def test_create_grant_success(client, db_engine, test_project):
    """Test successful grant creation."""
    from sqlalchemy.orm import sessionmaker
    from billing_service.models import Project
    
    TestingSessionLocal = sessionmaker(bind=db_engine)
    
    # Get fresh project from engine to avoid thread issues
    setup_db = TestingSessionLocal()
    try:
        fresh_project = setup_db.query(Project).filter(Project.id == test_project.id).first()
        # Ensure project exists with correct project_id
        if not fresh_project or fresh_project.project_id != "test-project":
            fresh_project.project_id = "test-project"
            setup_db.commit()
            setup_db.refresh(fresh_project)
    finally:
        setup_db.close()
    
    # Use FastAPI dependency override - create a new session per request for thread safety
    async def override_get_db():
        test_session = TestingSessionLocal()
        try:
            yield test_session
        finally:
            test_session.close()
    
    async def override_verify_admin():
        return "admin_user"
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_admin_api_key] = override_verify_admin
    
    try:
        response = await client.post(
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
        data = response.json()
        assert "grant_id" in data
        assert data["user_id"] == "user_123"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_grant_missing_reason(client, db_engine, test_project):
    """Test grant creation with missing reason."""
    from sqlalchemy.orm import sessionmaker
    TestingSessionLocal = sessionmaker(bind=db_engine)
    
    async def override_get_db():
        test_session = TestingSessionLocal()
        try:
            yield test_session
        finally:
            test_session.close()
    
    async def override_verify_admin():
        return "admin_user"
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_admin_api_key] = override_verify_admin
    
    try:
        response = await client.post(
            "/api/v1/admin/grant",
            headers={"Authorization": "Bearer admin_key_123"},
            json={
                "user_id": "user_123",
                "project_id": "test-project",
                "feature_code": "premium_feature",
                "reason": "",  # Empty reason
            },
        )
        
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_grant_project_not_found(client, db_engine):
    """Test grant creation with non-existent project."""
    from sqlalchemy.orm import sessionmaker
    TestingSessionLocal = sessionmaker(bind=db_engine)
    
    async def override_get_db():
        test_session = TestingSessionLocal()
        try:
            yield test_session
        finally:
            test_session.close()
    
    async def override_verify_admin():
        return "admin_user"
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_admin_api_key] = override_verify_admin
    
    try:
        response = await client.post(
            "/api/v1/admin/grant",
            headers={"Authorization": "Bearer admin_key_123"},
            json={
                "user_id": "user_123",
                "project_id": "nonexistent-project",
                "feature_code": "premium_feature",
                "reason": "Test grant",
            },
        )
        
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_grant_already_exists(client, db_engine, test_project):
    """Test grant creation when grant already exists."""
    from sqlalchemy.orm import sessionmaker
    from billing_service.models import Project
    TestingSessionLocal = sessionmaker(bind=db_engine)
    
    # Create existing grant first
    setup_db = TestingSessionLocal()
    try:
        fresh_project = setup_db.query(Project).filter(Project.id == test_project.id).first()
        existing_grant = ManualGrant(
            user_id="user_123",
            project_id=fresh_project.id,
            feature_code="premium_feature",
            valid_from=datetime.utcnow(),
            reason="Existing grant",
            granted_by="admin_user",
        )
        setup_db.add(existing_grant)
        setup_db.commit()
    finally:
        setup_db.close()
    
    async def override_get_db():
        test_session = TestingSessionLocal()
        try:
            yield test_session
        finally:
            test_session.close()
    
    async def override_verify_admin():
        return "admin_user"
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_admin_api_key] = override_verify_admin
    
    try:
        response = await client.post(
            "/api/v1/admin/grant",
            headers={"Authorization": "Bearer admin_key_123"},
            json={
                "user_id": "user_123",
                "project_id": "test-project",
                "feature_code": "premium_feature",
                "reason": "Test grant",
            },
        )
        
        assert response.status_code == 409
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_revoke_grant_not_found(client, db_engine):
    """Test grant revocation with non-existent grant."""
    from sqlalchemy.orm import sessionmaker
    TestingSessionLocal = sessionmaker(bind=db_engine)
    
    async def override_get_db():
        test_session = TestingSessionLocal()
        try:
            yield test_session
        finally:
            test_session.close()
    
    async def override_verify_admin():
        return "admin_user"
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_admin_api_key] = override_verify_admin
    
    try:
        import uuid
        response = await client.post(
            "/api/v1/admin/revoke",
            headers={"Authorization": "Bearer admin_key_123"},
            json={
                "grant_id": str(uuid.uuid4()),
                "revoke_reason": "Test revocation",
            },
        )
        
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_revoke_grant_already_revoked(client, db_engine, test_project):
    """Test grant revocation when grant is already revoked."""
    from sqlalchemy.orm import sessionmaker
    from billing_service.models import Project
    TestingSessionLocal = sessionmaker(bind=db_engine)
    
    # Create revoked grant first
    setup_db = TestingSessionLocal()
    try:
        fresh_project = setup_db.query(Project).filter(Project.id == test_project.id).first()
        revoked_grant = ManualGrant(
            user_id="user_123",
            project_id=fresh_project.id,
            feature_code="premium_feature",
            valid_from=datetime.utcnow(),
            reason="Test grant",
            granted_by="admin_user",
            revoked_at=datetime.utcnow(),
            revoked_by="admin_user",
            revoke_reason="Already revoked",
        )
        setup_db.add(revoked_grant)
        setup_db.commit()
        setup_db.refresh(revoked_grant)
        grant_id = revoked_grant.id
    finally:
        setup_db.close()
    
    async def override_get_db():
        test_session = TestingSessionLocal()
        try:
            yield test_session
        finally:
            test_session.close()
    
    async def override_verify_admin():
        return "admin_user"
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_admin_api_key] = override_verify_admin
    
    try:
        response = await client.post(
            "/api/v1/admin/revoke",
            headers={"Authorization": "Bearer admin_key_123"},
            json={
                "grant_id": str(grant_id),
                "revoke_reason": "Test revocation",
            },
        )
        
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_revoke_grant_missing_reason(client, db_engine, test_project):
    """Test grant revocation with missing reason."""
    from sqlalchemy.orm import sessionmaker
    from billing_service.models import Project
    TestingSessionLocal = sessionmaker(bind=db_engine)
    
    # Create grant first - ensure clean state by deleting any existing grants
    setup_db = TestingSessionLocal()
    try:
        fresh_project = setup_db.query(Project).filter(Project.id == test_project.id).first()
        # Delete any existing grants for this user/feature to avoid conflicts
        from billing_service.models import ManualGrant
        existing = setup_db.query(ManualGrant).filter(
            ManualGrant.user_id == "user_revoke_test",
            ManualGrant.project_id == fresh_project.id,
            ManualGrant.feature_code == "premium_feature",
        ).all()
        for g in existing:
            setup_db.delete(g)
        setup_db.commit()
        
        grant = ManualGrant(
            user_id="user_revoke_test",
            project_id=fresh_project.id,
            feature_code="premium_feature",
            valid_from=datetime.utcnow(),
            reason="Test grant",
            granted_by="admin_user",
        )
        setup_db.add(grant)
        setup_db.commit()
        setup_db.refresh(grant)
        grant_id = grant.id
    finally:
        setup_db.close()
    
    async def override_get_db():
        test_session = TestingSessionLocal()
        try:
            yield test_session
        finally:
            test_session.close()
    
    async def override_verify_admin():
        return "admin_user"
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_admin_api_key] = override_verify_admin
    
    try:
        response = await client.post(
            "/api/v1/admin/revoke",
            headers={"Authorization": "Bearer admin_key_123"},
            json={
                "grant_id": str(grant_id),
                "revoke_reason": "",  # Empty reason
            },
        )
        
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_revoke_grant_success(client, db_engine, test_project):
    """Test successful grant revocation."""
    # Create grant first using engine to avoid thread issues
    from sqlalchemy.orm import sessionmaker
    TestingSessionLocal = sessionmaker(bind=db_engine)
    setup_db = TestingSessionLocal()
    try:
        grant = ManualGrant(
            user_id="user_123",
            project_id=test_project.id,
            feature_code="premium_feature",
            valid_from=datetime.utcnow(),
            reason="Test grant",
            granted_by="admin_user",
        )
        setup_db.add(grant)
        setup_db.commit()
        setup_db.refresh(grant)
        grant_id = grant.id
    finally:
        setup_db.close()
    
    # Use FastAPI dependency override - create a new session per request for thread safety
    async def override_get_db():
        test_session = TestingSessionLocal()
        try:
            yield test_session
        finally:
            test_session.close()
    
    async def override_verify_admin():
        return "admin_user"
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_admin_api_key] = override_verify_admin
    
    try:
        response = await client.post(
            "/api/v1/admin/revoke",
            headers={"Authorization": "Bearer admin_key_123"},
            json={
                "grant_id": str(grant_id),
                "revoke_reason": "Test revocation",
            },
        )
        
        # Should succeed with proper mocking
        assert response.status_code == 200
        data = response.json()
        assert "grant_id" in data
        assert "revoked_at" in data
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_trigger_reconciliation(client, db_engine, test_project):
    """Test reconciliation trigger."""
    from unittest.mock import patch
    import billing_service.reconciliation as reconciliation_module
    from sqlalchemy.orm import sessionmaker
    
    # Create a sessionmaker from the engine for reconciliation
    ReconSessionLocal = sessionmaker(bind=db_engine)
    
    # Patch SessionLocal to use our test engine's sessionmaker
    original_session_local = reconciliation_module.SessionLocal
    reconciliation_module.SessionLocal = ReconSessionLocal
    
    try:
        # Use FastAPI dependency override
        async def override_verify_admin():
            return "admin_user"
        
        app.dependency_overrides[verify_admin_api_key] = override_verify_admin
        
        try:
            response = await client.post(
                "/api/v1/admin/reconcile",
                headers={"Authorization": "Bearer admin_key_123"},
            )
            
            # Should succeed - reconciliation runs with no data (all 0s)
            assert response.status_code == 200
            data = response.json()
            # With no subscriptions/purchases in DB, all counts should be 0
            assert data["subscriptions_synced"] == 0
            assert data["subscriptions_updated"] == 0
            assert data["subscriptions_missing_in_stripe"] == 0
            assert data["purchases_synced"] == 0
            assert data["purchases_updated"] == 0
            assert data["purchases_missing_in_stripe"] == 0
        finally:
            app.dependency_overrides.clear()
    finally:
        # Restore original SessionLocal
        reconciliation_module.SessionLocal = original_session_local
