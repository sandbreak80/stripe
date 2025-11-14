"""Additional error path and edge case tests for event processors."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from billing_service.event_processors import (
    CheckoutSessionCompletedProcessor,
    InvoicePaymentSucceededProcessor,
    CustomerSubscriptionUpdatedProcessor,
    CustomerSubscriptionDeletedProcessor,
    ChargeRefundedProcessor,
)
from billing_service.models import (
    Subscription,
    Purchase,
    SubscriptionStatus,
    PurchaseStatus,
)


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_checkout_session_missing_metadata(mock_invalidate, mock_recompute, mock_session_local, db_session):
    """Test checkout processor handles missing metadata gracefully."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = CheckoutSessionCompletedProcessor()
    
    mock_event = Mock()
    mock_session = Mock()
    mock_session.mode = "subscription"
    mock_session.metadata = {}  # Missing user_id and project_id
    mock_event.data.object = mock_session
    mock_event.id = "evt_test123"
    
    # Should not raise exception
    processor.process(mock_event)


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_checkout_session_missing_project(mock_invalidate, mock_recompute, mock_session_local, db_session):
    """Test checkout processor handles missing project gracefully."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = CheckoutSessionCompletedProcessor()
    
    mock_event = Mock()
    mock_session = Mock()
    mock_session.mode = "subscription"
    mock_session.metadata = {"user_id": "user_123", "project_id": "nonexistent"}
    mock_session.subscription = "sub_test123"
    mock_event.data.object = mock_session
    mock_event.id = "evt_test123"
    
    # Should not raise exception
    processor.process(mock_event)


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_checkout_session_missing_subscription_id(mock_invalidate, mock_recompute, mock_session_local, db_session, test_project):
    """Test checkout processor handles missing subscription ID gracefully."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = CheckoutSessionCompletedProcessor()
    
    mock_event = Mock()
    mock_session = Mock()
    mock_session.mode = "subscription"
    mock_session.metadata = {"user_id": "user_123", "project_id": test_project.project_id}
    mock_session.subscription = None  # Missing subscription ID
    mock_event.data.object = mock_session
    mock_event.id = "evt_test123"
    
    # Should not raise exception
    processor.process(mock_event)


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_checkout_session_stripe_api_failure(mock_invalidate, mock_recompute, mock_session_local, db_session, test_project):
    """Test checkout processor handles Stripe API failures gracefully."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = CheckoutSessionCompletedProcessor()
    
    mock_event = Mock()
    mock_session = Mock()
    mock_session.mode = "subscription"
    mock_session.metadata = {"user_id": "user_123", "project_id": test_project.project_id}
    mock_session.subscription = "sub_test123"
    mock_event.data.object = mock_session
    mock_event.id = "evt_test123"
    
    # Mock Stripe API failure
    with patch('stripe.Subscription.retrieve', side_effect=Exception("Stripe API error")):
        # Should not raise exception
        processor.process(mock_event)


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_checkout_session_missing_price(mock_invalidate, mock_recompute, mock_session_local, db_session, test_project):
    """Test checkout processor handles missing price gracefully."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = CheckoutSessionCompletedProcessor()
    
    mock_event = Mock()
    mock_session = Mock()
    mock_session.mode = "subscription"
    mock_session.metadata = {"user_id": "user_123", "project_id": test_project.project_id}
    mock_session.subscription = "sub_test123"
    mock_event.data.object = mock_session
    mock_event.id = "evt_test123"
    
    # Mock Stripe subscription with nonexistent price
    mock_stripe_sub = Mock()
    mock_stripe_sub.id = "sub_test123"
    mock_stripe_sub.status = "active"
    mock_stripe_sub.current_period_start = int(datetime.utcnow().timestamp())
    mock_stripe_sub.current_period_end = int((datetime.utcnow().timestamp() + 86400 * 30))
    mock_stripe_sub.items.data = [Mock()]
    mock_stripe_sub.items.data[0].price.id = "price_nonexistent"
    
    with patch('stripe.Subscription.retrieve', return_value=mock_stripe_sub):
        with patch('stripe.api_key', 'test_key'):
            # Should not raise exception
            processor.process(mock_event)


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_checkout_payment_missing_payment_intent(mock_invalidate, mock_recompute, mock_session_local, db_session, test_project):
    """Test checkout processor handles missing payment intent gracefully."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = CheckoutSessionCompletedProcessor()
    
    mock_event = Mock()
    mock_session = Mock()
    mock_session.mode = "payment"
    mock_session.metadata = {"user_id": "user_123", "project_id": test_project.project_id}
    mock_session.payment_intent = None  # Missing payment intent
    mock_event.data.object = mock_session
    mock_event.id = "evt_test123"
    
    # Should not raise exception
    processor.process(mock_event)


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_checkout_payment_missing_charges(mock_invalidate, mock_recompute, mock_session_local, db_session, test_project):
    """Test checkout processor handles missing charges gracefully."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = CheckoutSessionCompletedProcessor()
    
    mock_event = Mock()
    mock_session = Mock()
    mock_session.mode = "payment"
    mock_session.metadata = {"user_id": "user_123", "project_id": test_project.project_id}
    mock_session.payment_intent = "pi_test123"
    mock_session.id = "cs_test123"
    mock_event.data.object = mock_session
    mock_event.id = "evt_test123"
    
    # Mock payment intent with no charges
    mock_payment_intent = Mock()
    mock_payment_intent.charges.data = []  # No charges
    
    with patch('stripe.PaymentIntent.retrieve', return_value=mock_payment_intent):
        # Should not raise exception
        processor.process(mock_event)


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_invoice_payment_no_subscription(mock_invalidate, mock_recompute, mock_session_local, db_session):
    """Test invoice processor handles invoice without subscription gracefully."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = InvoicePaymentSucceededProcessor()
    
    mock_event = Mock()
    mock_event.id = "evt_test123"
    mock_invoice = Mock()
    mock_invoice.subscription = None  # No subscription
    mock_event.data.object = mock_invoice
    
    # Should not raise exception
    processor.process(mock_event)


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_invoice_payment_subscription_not_found(mock_invalidate, mock_recompute, mock_session_local, db_session):
    """Test invoice processor handles missing subscription gracefully."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = InvoicePaymentSucceededProcessor()
    
    mock_event = Mock()
    mock_event.id = "evt_test123"
    mock_invoice = Mock()
    mock_invoice.subscription = "sub_nonexistent"
    mock_invoice.customer = "cus_test123"
    mock_event.data.object = mock_invoice
    
    # Should not raise exception
    processor.process(mock_event)


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_subscription_updated_missing_id(mock_invalidate, mock_recompute, mock_session_local, db_session):
    """Test subscription updated processor handles missing subscription ID gracefully."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = CustomerSubscriptionUpdatedProcessor()
    
    mock_event = Mock()
    mock_event.id = "evt_test123"
    mock_subscription = Mock()
    mock_subscription.id = None  # Missing ID
    mock_event.data.object = mock_subscription
    
    # Should not raise exception
    processor.process(mock_event)


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_subscription_updated_not_found(mock_invalidate, mock_recompute, mock_session_local, db_session):
    """Test subscription updated processor handles missing subscription gracefully."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = CustomerSubscriptionUpdatedProcessor()
    
    mock_event = Mock()
    mock_event.id = "evt_test123"
    mock_subscription = Mock()
    mock_subscription.id = "sub_nonexistent"
    mock_subscription.status = "active"
    mock_event.data.object = mock_subscription
    
    # Should not raise exception
    processor.process(mock_event)


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_subscription_deleted_missing_id(mock_invalidate, mock_recompute, mock_session_local, db_session):
    """Test subscription deleted processor handles missing subscription ID gracefully."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = CustomerSubscriptionDeletedProcessor()
    
    mock_event = Mock()
    mock_event.id = "evt_test123"
    mock_subscription = Mock()
    mock_subscription.id = None  # Missing ID
    mock_event.data.object = mock_subscription
    
    # Should not raise exception
    processor.process(mock_event)


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_subscription_deleted_not_found(mock_invalidate, mock_recompute, mock_session_local, db_session):
    """Test subscription deleted processor handles missing subscription gracefully."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = CustomerSubscriptionDeletedProcessor()
    
    mock_event = Mock()
    mock_event.id = "evt_test123"
    mock_subscription = Mock()
    mock_subscription.id = "sub_nonexistent"
    mock_event.data.object = mock_subscription
    
    # Should not raise exception
    processor.process(mock_event)


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_charge_refunded_missing_id(mock_invalidate, mock_recompute, mock_session_local, db_session):
    """Test charge refunded processor handles missing charge ID gracefully."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = ChargeRefundedProcessor()
    
    mock_event = Mock()
    mock_event.id = "evt_test123"
    mock_charge = Mock()
    mock_charge.id = None  # Missing ID
    mock_event.data.object = mock_charge
    
    # Should not raise exception
    processor.process(mock_event)
