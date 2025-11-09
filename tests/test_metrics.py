"""Tests for metrics API."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from billing_service.database import Base, get_db
from billing_service.main import app
from billing_service.models import App, Project, Purchase, Subscription


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


def test_get_project_subscriptions(client_with_db, test_app, test_project, db_session):
    """Test get project subscriptions metrics."""
    # Create test subscription
    from billing_service.models import User
    user = User(project_id=test_project.id, external_user_id="user_123")
    db_session.add(user)
    db_session.commit()
    
    subscription = Subscription(
        user_id=user.id,
        project_id=test_project.id,
        stripe_subscription_id="sub_test",
        stripe_price_id="price_test",
        status="active",
    )
    db_session.add(subscription)
    db_session.commit()
    
    response = client_with_db.get(
        f"/api/v1/metrics/project/{test_project.id}/subscriptions",
        headers={"X-API-Key": test_app.api_key},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == test_project.id
    assert data["active_subscriptions"] >= 0


def test_get_project_revenue(client_with_db, test_app, test_project, db_session):
    """Test get project revenue metrics."""
    # Create test purchase
    from billing_service.models import User
    user = User(project_id=test_project.id, external_user_id="user_123")
    db_session.add(user)
    db_session.commit()
    
    purchase = Purchase(
        user_id=user.id,
        project_id=test_project.id,
        stripe_payment_intent_id="pi_test",
        stripe_price_id="price_test",
        amount=1000,
        status="succeeded",
    )
    db_session.add(purchase)
    db_session.commit()
    
    response = client_with_db.get(
        f"/api/v1/metrics/project/{test_project.id}/revenue",
        headers={"X-API-Key": test_app.api_key},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == test_project.id
    assert "total_revenue_cents" in data
