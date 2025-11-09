"""Integration tests for webhook endpoints."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from billing_service.database import Base, get_db
from billing_service.main import app
from billing_service.models import (
    App,
    Project,
    Purchase,
    StripeCustomer,
    Subscription,
    User,
    WebhookEvent,
)


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
def test_stripe_customer(db_session, test_user):
    """Create a test Stripe customer."""
    stripe_customer = StripeCustomer(
        user_id=test_user.id,
        stripe_customer_id="cus_test123",
    )
    db_session.add(stripe_customer)
    db_session.commit()
    db_session.refresh(stripe_customer)
    return stripe_customer


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


def create_webhook_signature(payload: str, secret: str) -> str:
    """Create a valid Stripe webhook signature for testing."""
    import hmac
    import hashlib
    import time
    
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{payload}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    return f"t={timestamp},v1={signature}"


def test_webhook_missing_signature(client_with_db):
    """Test webhook with missing signature."""
    response = client_with_db.post(
        "/api/v1/webhooks/stripe",
        json={"id": "evt_test", "type": "payment_intent.succeeded"},
    )
    
    assert response.status_code == 400


def test_webhook_invalid_signature(client_with_db):
    """Test webhook with invalid signature."""
    payload = json.dumps({"id": "evt_test", "type": "payment_intent.succeeded"})
    
    response = client_with_db.post(
        "/api/v1/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": "invalid_signature"},
    )
    
    assert response.status_code == 401


def test_webhook_payment_intent_succeeded(
    client_with_db,
    db_session,
    test_user,
    test_stripe_customer,
):
    """Test processing payment_intent.succeeded webhook."""
    event_data = {
        "id": "evt_test123",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_test123",
                "customer": "cus_test123",
                "amount": 1000,
                "currency": "usd",
                "metadata": {"price_id": "price_test123"},
            }
        },
    }
    
    payload = json.dumps(event_data)
    signature = create_webhook_signature(payload, "whsec_placeholder")
    
    response = client_with_db.post(
        "/api/v1/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )
    
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    
    # Verify event was stored
    webhook_event = (
        db_session.query(WebhookEvent)
        .filter(WebhookEvent.stripe_event_id == "evt_test123")
        .first()
    )
    assert webhook_event is not None
    assert webhook_event.processed is True
    
    # Verify purchase was created
    purchase = (
        db_session.query(Purchase)
        .filter(Purchase.stripe_payment_intent_id == "pi_test123")
        .first()
    )
    assert purchase is not None
    assert purchase.status == "succeeded"
    assert purchase.amount == 1000


def test_webhook_subscription_created(
    client_with_db,
    db_session,
    test_user,
    test_stripe_customer,
):
    """Test processing customer.subscription.created webhook."""
    event_data = {
        "id": "evt_test456",
        "type": "customer.subscription.created",
        "data": {
            "object": {
                "id": "sub_test123",
                "customer": "cus_test123",
                "status": "active",
                "current_period_start": int(datetime.now().timestamp()),
                "current_period_end": int(datetime.now().timestamp()) + 2592000,  # 30 days
                "cancel_at_period_end": False,
                "items": {
                    "data": [{"price": {"id": "price_test123"}}]
                },
            }
        },
    }
    
    payload = json.dumps(event_data)
    signature = create_webhook_signature(payload, "whsec_placeholder")
    
    response = client_with_db.post(
        "/api/v1/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )
    
    assert response.status_code == 200
    
    # Verify subscription was created
    subscription = (
        db_session.query(Subscription)
        .filter(Subscription.stripe_subscription_id == "sub_test123")
        .first()
    )
    assert subscription is not None
    assert subscription.status == "active"


def test_webhook_idempotency(
    client_with_db,
    db_session,
    test_user,
    test_stripe_customer,
):
    """Test webhook idempotency - processing same event twice."""
    event_data = {
        "id": "evt_idempotent",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_idempotent",
                "customer": "cus_test123",
                "amount": 2000,
                "currency": "usd",
                "metadata": {"price_id": "price_test123"},
            }
        },
    }
    
    payload = json.dumps(event_data)
    signature = create_webhook_signature(payload, "whsec_placeholder")
    
    # First request
    response1 = client_with_db.post(
        "/api/v1/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )
    assert response1.status_code == 200
    
    # Second request with same event
    response2 = client_with_db.post(
        "/api/v1/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )
    assert response2.status_code == 200
    assert response2.json() == {"status": "ok", "message": "Event already processed"}
    
    # Verify only one purchase was created
    purchases = db_session.query(Purchase).filter(Purchase.stripe_payment_intent_id == "pi_idempotent").all()
    assert len(purchases) == 1


def test_webhook_subscription_updated(
    client_with_db,
    db_session,
    test_user,
    test_stripe_customer,
):
    """Test processing customer.subscription.updated webhook."""
    # Create existing subscription
    subscription = Subscription(
        user_id=test_user.id,
        project_id=test_user.project_id,
        stripe_subscription_id="sub_update_test",
        stripe_price_id="price_test123",
        status="active",
        current_period_end=datetime.now(),
    )
    db_session.add(subscription)
    db_session.commit()
    
    event_data = {
        "id": "evt_update",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_update_test",
                "status": "past_due",
                "current_period_start": int(datetime.now().timestamp()),
                "current_period_end": int(datetime.now().timestamp()) + 2592000,
                "cancel_at_period_end": True,
            }
        },
    }
    
    payload = json.dumps(event_data)
    signature = create_webhook_signature(payload, "whsec_placeholder")
    
    response = client_with_db.post(
        "/api/v1/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )
    
    assert response.status_code == 200
    
    # Verify subscription was updated
    db_session.refresh(subscription)
    assert subscription.status == "past_due"
    assert subscription.cancel_at_period_end is True


def test_webhook_subscription_deleted(
    client_with_db,
    db_session,
    test_user,
    test_stripe_customer,
):
    """Test processing customer.subscription.deleted webhook."""
    # Create existing subscription
    subscription = Subscription(
        user_id=test_user.id,
        project_id=test_user.project_id,
        stripe_subscription_id="sub_delete_test",
        stripe_price_id="price_test123",
        status="active",
    )
    db_session.add(subscription)
    db_session.commit()
    
    event_data = {
        "id": "evt_delete",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_delete_test",
            }
        },
    }
    
    payload = json.dumps(event_data)
    signature = create_webhook_signature(payload, "whsec_placeholder")
    
    response = client_with_db.post(
        "/api/v1/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": signature, "content-type": "application/json"},
    )
    
    assert response.status_code == 200
    
    # Verify subscription status was updated (non-destructive)
    db_session.refresh(subscription)
    assert subscription.status == "canceled"
