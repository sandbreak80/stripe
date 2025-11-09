"""Integration tests for payment endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from billing_service.database import Base, get_db
from billing_service.main import app
from billing_service.models import App, Project, StripeCustomer, User


@pytest.fixture(scope="function")
def db_session():
    """Create a test database session."""
    import tempfile
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Use a temporary file-based database for better thread safety
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
    app_obj = App(
        project_id=test_project.id,
        name="test_app",
        api_key="test_api_key_123",
        active=True,
    )
    db_session.add(app_obj)
    db_session.commit()
    db_session.refresh(app_obj)
    return app_obj


@pytest.fixture(scope="function")
def test_user(db_session, test_project):
    """Create a test user."""
    user = User(
        project_id=test_project.id,
        external_user_id="user_123",
        email="test@example.com",
    )
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


@patch("billing_service.stripe_service.stripe.Customer.create")
@patch("billing_service.stripe_service.stripe.checkout.Session.create")
def test_create_checkout_session(
    mock_session_create,
    mock_customer_create,
    client_with_db,
    test_app,
    test_project,
):
    """Test checkout session creation."""
    # Mock Stripe responses
    mock_customer = MagicMock()
    mock_customer.id = "cus_test123"
    mock_customer_create.return_value = mock_customer

    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/test"
    mock_session_create.return_value = mock_session

    # Create request
    response = client_with_db.post(
        "/api/v1/checkout/session",
        json={
            "user_id": "user_123",
            "project_id": test_project.id,
            "price_id": "price_test123",
            "mode": "subscription",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        },
        headers={"X-API-Key": test_app.api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert "checkout_url" in data
    assert data["checkout_url"] == "https://checkout.stripe.com/test"


@patch("billing_service.stripe_service.stripe.billing_portal.Session.create")
def test_create_portal_session(
    mock_portal_create,
    client_with_db,
    test_app,
    test_project,
    test_user,
    db_session,
):
    """Test portal session creation."""
    # Create Stripe customer
    stripe_customer = StripeCustomer(
        user_id=test_user.id,
        stripe_customer_id="cus_test123",
    )
    db_session.add(stripe_customer)
    db_session.commit()

    # Mock Stripe response
    mock_session = MagicMock()
    mock_session.url = "https://billing.stripe.com/test"
    mock_portal_create.return_value = mock_session

    # Create request
    response = client_with_db.post(
        "/api/v1/portal/session",
        json={
            "user_id": "user_123",
            "project_id": test_project.id,
            "return_url": "https://example.com/return",
        },
        headers={"X-API-Key": test_app.api_key},
    )

    assert response.status_code == 200
    data = response.json()
    assert "portal_url" in data
    assert data["portal_url"] == "https://billing.stripe.com/test"


def test_checkout_session_invalid_api_key(client_with_db, db_session):
    """Test checkout session with invalid API key."""
    # Ensure we have a project in the database for the test
    project = Project(name="test_project", active=True)
    db_session.add(project)
    db_session.commit()
    
    response = client_with_db.post(
        "/api/v1/checkout/session",
        json={
            "user_id": "user_123",
            "project_id": project.id,
            "price_id": "price_test123",
            "mode": "subscription",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        },
        headers={"X-API-Key": "invalid_key"},
    )

    assert response.status_code == 401


def test_checkout_session_wrong_project(client_with_db, test_app, test_project, db_session):
    """Test checkout session with wrong project ID."""
    # Create another project
    other_project = Project(name="other_project", active=True)
    db_session.add(other_project)
    db_session.commit()
    db_session.refresh(other_project)

    response = client_with_db.post(
        "/api/v1/checkout/session",
        json={
            "user_id": "user_123",
            "project_id": other_project.id,
            "price_id": "price_test123",
            "mode": "subscription",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        },
        headers={"X-API-Key": test_app.api_key},
    )

    assert response.status_code == 403
