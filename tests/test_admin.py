"""Tests for admin API."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from billing_service.database import Base, get_db
from billing_service.main import app
from billing_service.models import App, Project, User


@pytest.fixture(scope="function")
def db_session():
    """Create a test database session."""
    import tempfile
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine)
    session = session_local()
    try:
        yield session
        session.rollback()
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        os.unlink(db_path)


@pytest.fixture(scope="function")
def test_project(db_session):
    """Create a test project."""
    project = Project(name="test_project", active=True)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture(scope="function")
def test_app(db_session, test_project):
    """Create a test app."""
    app_obj = App(project_id=test_project.id, name="test_app", api_key="test_api_key", active=True)
    db_session.add(app_obj)
    db_session.commit()
    db_session.refresh(app_obj)
    return app_obj


@pytest.fixture(scope="function")
def test_user(db_session, test_project):
    """Create a test user."""
    user = User(project_id=test_project.id, external_user_id="user_123", email="test@example.com")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def client_with_db(db_session):
    """Create a test client with database override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    
    yield TestClient(app)
    app.dependency_overrides.clear()


@patch("billing_service.admin.recompute_and_store_entitlements")
@patch("billing_service.admin.invalidate_entitlements_cache")
def test_grant_entitlement(mock_invalidate, mock_recompute, client_with_db, test_app, test_project, test_user):
    """Test grant entitlement endpoint."""
    response = client_with_db.post(
        "/api/v1/admin/grant",
        json={
            "user_id": "user_123",
            "project_id": test_project.id,
            "feature_code": "premium",
            "granted_by": "admin@example.com",
            "reason": "Test grant",
        },
        headers={"X-API-Key": test_app.api_key},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "granted"
    mock_recompute.assert_called_once()
    mock_invalidate.assert_called_once()


@patch("billing_service.admin.recompute_and_store_entitlements")
@patch("billing_service.admin.invalidate_entitlements_cache")
def test_revoke_entitlement(mock_invalidate, mock_recompute, client_with_db, test_app, test_project, test_user):
    """Test revoke entitlement endpoint."""
    response = client_with_db.post(
        "/api/v1/admin/revoke",
        json={
            "user_id": "user_123",
            "project_id": test_project.id,
            "feature_code": "premium",
            "granted_by": "admin@example.com",
            "reason": "Test revoke",
        },
        headers={"X-API-Key": test_app.api_key},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "revoked"
    mock_recompute.assert_called_once()
    mock_invalidate.assert_called_once()
