"""Additional tests for entitlements API edge cases."""

from datetime import datetime, timedelta
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


@patch("billing_service.entitlements_api.compute_entitlements")
@patch("billing_service.entitlements_api.set_entitlements_in_cache")
def test_get_entitlements_not_cached(mock_set_cache, mock_compute, client_with_db, test_app, test_project, test_user):
    """Test entitlements endpoint without cache."""
    mock_compute.return_value = [
        {
            "feature_code": "premium",
            "active": True,
            "source": "subscription",
            "source_id": 1,
            "valid_from": datetime.utcnow(),
            "valid_to": datetime.utcnow() + timedelta(days=30),
        }
    ]
    
    response = client_with_db.get(
        "/api/v1/entitlements",
        params={"user_id": "user_123", "project_id": test_project.id},
        headers={"X-API-Key": test_app.api_key},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "entitlements" in data
    assert len(data["entitlements"]) > 0
    mock_compute.assert_called_once()
    mock_set_cache.assert_called_once()


def test_get_entitlements_wrong_project(client_with_db, test_app, test_project, db_session):
    """Test entitlements endpoint with wrong project."""
    # Create another project
    other_project = Project(name="other_project", active=True)
    db_session.add(other_project)
    db_session.commit()
    db_session.refresh(other_project)
    
    response = client_with_db.get(
        "/api/v1/entitlements",
        params={"user_id": "user_123", "project_id": other_project.id},
        headers={"X-API-Key": test_app.api_key},
    )
    
    assert response.status_code == 403


def test_get_entitlements_no_user(client_with_db, test_app, test_project):
    """Test entitlements endpoint with non-existent user."""
    response = client_with_db.get(
        "/api/v1/entitlements",
        params={"user_id": "nonexistent", "project_id": test_project.id},
        headers={"X-API-Key": test_app.api_key},
    )
    
    assert response.status_code == 404
