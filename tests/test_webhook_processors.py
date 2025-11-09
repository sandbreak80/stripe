"""Unit tests for webhook processors."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from billing_service.models import Purchase, StripeCustomer, Subscription, User
from billing_service.webhook_processors import (
    process_charge_refunded,
    process_invoice_payment_failed,
    process_invoice_payment_succeeded,
    process_payment_intent_failed,
    process_payment_intent_succeeded,
    process_subscription_created,
    process_subscription_deleted,
    process_subscription_updated,
)


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def test_user():
    """Create a test user object."""
    from billing_service.models import Project
    
    project = Project(id=1, name="test_project", active=True)
    user = User(id=1, project_id=1, external_user_id="user_123", email="test@example.com")
    user.project = project
    return user


@pytest.fixture
def test_stripe_customer(test_user):
    """Create a test Stripe customer."""
    stripe_customer = StripeCustomer(
        id=1,
        user_id=1,
        stripe_customer_id="cus_test123",
    )
    stripe_customer.user = test_user
    return stripe_customer


@patch("billing_service.webhook_processors.recompute_and_store_entitlements")
@patch("billing_service.webhook_processors.invalidate_entitlements_cache")
@patch("billing_service.webhook_processors.stripe.Invoice.retrieve")
def test_process_payment_intent_succeeded_with_invoice(
    mock_invoice_retrieve,
    mock_invalidate,
    mock_recompute,
    mock_db_session,
    test_stripe_customer,
):
    """Test payment_intent.succeeded with invoice."""
    # Mock customer query
    customer_query = MagicMock()
    customer_query.filter.return_value.first.return_value = test_stripe_customer
    
    # Mock purchase query (doesn't exist)
    purchase_query = MagicMock()
    purchase_query.filter.return_value.first.return_value = None
    
    # Set up query to return different results for different models
    def query_side_effect(model):
        if model == StripeCustomer:
            return customer_query
        elif model == Purchase:
            return purchase_query
        return MagicMock()
    
    mock_db_session.query.side_effect = query_side_effect
    
    # Mock invoice retrieval
    mock_invoice = MagicMock()
    mock_price = MagicMock()
    mock_price.id = "price_from_invoice"
    mock_line = MagicMock()
    mock_line.price = mock_price
    mock_invoice.lines.data = [mock_line]
    mock_invoice_retrieve.return_value = mock_invoice
    
    event_data = {
        "data": {
            "object": {
                "id": "pi_test123",
                "customer": "cus_test123",
                "amount": 1000,
                "currency": "usd",
                "invoice": "in_test123",
            }
        }
    }
    
    process_payment_intent_succeeded(event_data, mock_db_session)
    
    # Verify purchase was added
    mock_db_session.add.assert_called_once()
    # Commit is called: once for purchase, once in recompute_and_store_entitlements
    assert mock_db_session.commit.call_count >= 1
    # Verify entitlements were recomputed
    mock_recompute.assert_called_once()
    mock_invalidate.assert_called_once()


def test_process_payment_intent_succeeded_idempotent(mock_db_session, test_stripe_customer):
    """Test payment_intent.succeeded idempotency."""
    mock_db_session.query.return_value.filter.return_value.first.side_effect = [
        test_stripe_customer,  # Customer query
        Purchase(id=1, stripe_payment_intent_id="pi_test123", status="succeeded"),  # Existing purchase
    ]
    
    event_data = {
        "data": {
            "object": {
                "id": "pi_test123",
                "customer": "cus_test123",
                "amount": 1000,
                "currency": "usd",
                "metadata": {"price_id": "price_test123"},
            }
        }
    }
    
    process_payment_intent_succeeded(event_data, mock_db_session)
    
    # Should not add new purchase
    mock_db_session.add.assert_not_called()


@patch("billing_service.webhook_processors.recompute_and_store_entitlements")
@patch("billing_service.webhook_processors.invalidate_entitlements_cache")
def test_process_payment_intent_failed(
    mock_invalidate,
    mock_recompute,
    mock_db_session,
):
    """Test payment_intent.payment_failed."""
    existing_purchase = Purchase(
        id=1,
        stripe_payment_intent_id="pi_failed",
        status="pending",
        user_id=1,
        project_id=1,
    )
    mock_db_session.query.return_value.filter.return_value.first.return_value = existing_purchase
    
    event_data = {
        "data": {
            "object": {
                "id": "pi_failed",
            }
        }
    }
    
    process_payment_intent_failed(event_data, mock_db_session)
    
    assert existing_purchase.status == "failed"
    # Commit is called: once for purchase update, once in recompute_and_store_entitlements
    assert mock_db_session.commit.call_count >= 1
    mock_recompute.assert_called_once()
    mock_invalidate.assert_called_once()


def test_process_subscription_created_idempotent(mock_db_session, test_stripe_customer):
    """Test subscription.created idempotency."""
    mock_db_session.query.return_value.filter.return_value.first.side_effect = [
        test_stripe_customer,  # Customer query
        Subscription(id=1, stripe_subscription_id="sub_existing"),  # Existing subscription
    ]
    
    event_data = {
        "data": {
            "object": {
                "id": "sub_existing",
                "customer": "cus_test123",
                "status": "active",
                "items": {"data": [{"price": {"id": "price_test123"}}]},
            }
        }
    }
    
    process_subscription_created(event_data, mock_db_session)
    
    # Should not add new subscription
    mock_db_session.add.assert_not_called()


def test_process_subscription_updated_not_found(mock_db_session):
    """Test subscription.updated when subscription doesn't exist."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    
    event_data = {
        "data": {
            "object": {
                "id": "sub_new",
                "customer": "cus_test123",
                "status": "active",
            }
        }
    }
    
    # Should call subscription.created processor
    with patch(
        "billing_service.webhook_processors.process_subscription_created"
    ) as mock_create:
        process_subscription_updated(event_data, mock_db_session)
        mock_create.assert_called_once()


@patch("billing_service.webhook_processors.recompute_and_store_entitlements")
@patch("billing_service.webhook_processors.invalidate_entitlements_cache")
def test_process_invoice_payment_succeeded(
    mock_invalidate,
    mock_recompute,
    mock_db_session,
):
    """Test invoice.payment_succeeded."""
    subscription = Subscription(
        id=1,
        stripe_subscription_id="sub_test",
        status="past_due",
        user_id=1,
        project_id=1,
    )
    mock_db_session.query.return_value.filter.return_value.first.return_value = subscription
    
    event_data = {
        "data": {
            "object": {
                "subscription": "sub_test",
                "period_start": int(datetime.now().timestamp()),
                "period_end": int(datetime.now().timestamp()) + 2592000,
            }
        }
    }
    
    process_invoice_payment_succeeded(event_data, mock_db_session)
    
    assert subscription.status == "active"
    # Commit is called: once for subscription update, once in recompute_and_store_entitlements
    assert mock_db_session.commit.call_count >= 1
    mock_recompute.assert_called_once()
    mock_invalidate.assert_called_once()


@patch("billing_service.webhook_processors.recompute_and_store_entitlements")
@patch("billing_service.webhook_processors.invalidate_entitlements_cache")
def test_process_invoice_payment_failed(
    mock_invalidate,
    mock_recompute,
    mock_db_session,
):
    """Test invoice.payment_failed."""
    subscription = Subscription(
        id=1,
        stripe_subscription_id="sub_test",
        status="active",
        user_id=1,
        project_id=1,
    )
    mock_db_session.query.return_value.filter.return_value.first.return_value = subscription
    
    event_data = {
        "data": {
            "object": {
                "subscription": "sub_test",
            }
        }
    }
    
    process_invoice_payment_failed(event_data, mock_db_session)
    
    assert subscription.status == "past_due"
    # Commit is called: once for subscription update, once in recompute_and_store_entitlements
    assert mock_db_session.commit.call_count >= 1
    mock_recompute.assert_called_once()
    mock_invalidate.assert_called_once()


@patch("billing_service.webhook_processors.recompute_and_store_entitlements")
@patch("billing_service.webhook_processors.invalidate_entitlements_cache")
def test_process_charge_refunded(
    mock_invalidate,
    mock_recompute,
    mock_db_session,
):
    """Test charge.refunded."""
    purchase = Purchase(
        id=1,
        stripe_payment_intent_id="pi_refunded",
        status="succeeded",
        user_id=1,
        project_id=1,
    )
    mock_db_session.query.return_value.filter.return_value.first.return_value = purchase
    
    event_data = {
        "data": {
            "object": {
                "payment_intent": "pi_refunded",
            }
        }
    }
    
    process_charge_refunded(event_data, mock_db_session)
    
    assert purchase.status == "refunded"
    # Commit is called: once for purchase update, once in recompute_and_store_entitlements
    assert mock_db_session.commit.call_count >= 1
    mock_recompute.assert_called_once()
    mock_invalidate.assert_called_once()
