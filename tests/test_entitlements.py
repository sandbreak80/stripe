"""Tests for entitlements API."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from billing_service.database import Base, get_db
from billing_service.main import app
from billing_service.models import App, Price, Product, Project, User


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


@patch("billing_service.entitlements_api.get_entitlements_from_cache")
@patch("billing_service.entitlements_api.compute_entitlements")
def test_get_entitlements_cached(mock_compute, mock_cache, client_with_db, test_app, test_project, test_user):
    """Test entitlements endpoint with cache hit."""
    mock_cache.return_value = [{"feature_code": "premium", "active": True, "source": "subscription"}]
    
    response = client_with_db.get(
        "/api/v1/entitlements",
        params={"user_id": "user_123", "project_id": test_project.id},
        headers={"X-API-Key": test_app.api_key},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "entitlements" in data
    mock_cache.assert_called_once()
    mock_compute.assert_not_called()


def test_get_entitlements_no_user(client_with_db, test_app, test_project):
    """Test entitlements endpoint with non-existent user."""
    response = client_with_db.get(
        "/api/v1/entitlements",
        params={"user_id": "nonexistent", "project_id": test_project.id},
        headers={"X-API-Key": test_app.api_key},
    )
    
    assert response.status_code == 404
