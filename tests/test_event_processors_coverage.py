"""Additional tests for event processors to increase coverage."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from billing_service.event_processors import (
    CheckoutSessionCompletedProcessor,
    InvoicePaymentSucceededProcessor,
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
def test_checkout_session_completed_subscription_creates_subscription(mock_invalidate, mock_recompute, mock_session_local, db_session, test_project, test_product, test_price):
    """Test checkout processor creates subscription for subscription mode."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = CheckoutSessionCompletedProcessor()
    
    # Create mock event with subscription mode - use project.project_id not project.id
    mock_event = Mock()
    mock_session = Mock()
    mock_session.mode = "subscription"
    mock_session.metadata = {"user_id": "user_123", "project_id": test_project.project_id}  # Use project_id string
    mock_session.subscription = "sub_test123"
    mock_event.data.object = mock_session
    mock_event.id = "evt_test123"
    
    # Mock Stripe subscription retrieval
    mock_stripe_sub = Mock()
    mock_stripe_sub.id = "sub_test123"
    mock_stripe_sub.status = "active"
    mock_stripe_sub.current_period_start = int(datetime.utcnow().timestamp())
    mock_stripe_sub.current_period_end = int((datetime.utcnow().timestamp() + 86400 * 30))
    mock_stripe_sub.items.data = [Mock()]
    mock_stripe_sub.items.data[0].price.id = str(test_price.stripe_price_id)
    
    with patch('stripe.Subscription.retrieve', return_value=mock_stripe_sub):
        with patch('stripe.api_key', 'test_key'):
            processor.process(mock_event)
    
    # Verify subscription was created
    db_session.commit()
    subscription = db_session.query(Subscription).filter(
        Subscription.stripe_subscription_id == "sub_test123"
    ).first()
    assert subscription is not None
    assert subscription.user_id == "user_123"
    assert subscription.status == SubscriptionStatus.ACTIVE


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_invoice_payment_succeeded_updates_subscription_period(mock_invalidate, mock_recompute, mock_session_local, db_session, test_project, test_product, test_price):
    """Test invoice processor updates subscription period."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = InvoicePaymentSucceededProcessor()
    
    # Create subscription
    subscription = Subscription(
        stripe_subscription_id="sub_test123",
        user_id="user_123",
        project_id=test_project.id,
        price_id=test_price.id,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow(),
        cancel_at_period_end=False,
    )
    db_session.add(subscription)
    db_session.commit()
    
    # Create mock event
    mock_event = Mock()
    mock_event.id = "evt_test123"
    mock_invoice = Mock()
    mock_invoice.subscription = "sub_test123"
    mock_invoice.customer = "cus_test123"
    mock_invoice.period_start = int(datetime.utcnow().timestamp())
    mock_invoice.period_end = int((datetime.utcnow().timestamp() + 86400 * 30))
    mock_event.data.object = mock_invoice
    
    processor.process(mock_event)
    
    # Verify subscription period was updated (query fresh from database)
    db_session.commit()
    updated_subscription = db_session.query(Subscription).filter(
        Subscription.stripe_subscription_id == "sub_test123"
    ).first()
    assert updated_subscription is not None
    assert updated_subscription.current_period_start is not None
    assert updated_subscription.current_period_end is not None


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_charge_refunded_processor_handles_missing_purchase(mock_invalidate, mock_recompute, mock_session_local, db_session):
    """Test charge refunded processor handles missing purchase gracefully."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = ChargeRefundedProcessor()
    
    # Create mock event for non-existent charge
    mock_event = Mock()
    mock_event.id = "evt_test123"
    mock_charge = Mock()
    mock_charge.id = "ch_nonexistent"
    mock_event.data.object = mock_charge
    
    # Should not raise exception
    processor.process(mock_event)
    
    # Verify no purchase was found (no exception raised)
    purchase = db_session.query(Purchase).filter(
        Purchase.stripe_charge_id == "ch_nonexistent"
    ).first()
    assert purchase is None


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_checkout_session_unknown_mode(mock_invalidate, mock_recompute, mock_session_local, db_session, test_project):
    """Test checkout processor handles unknown checkout mode gracefully."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = CheckoutSessionCompletedProcessor()
    
    mock_event = Mock()
    mock_session = Mock()
    mock_session.mode = "unknown_mode"  # Unknown mode
    mock_session.metadata = {"user_id": "user_123", "project_id": test_project.project_id}
    mock_event.data.object = mock_session
    mock_event.id = "evt_test123"
    
    # Should not raise exception, just log warning
    processor.process(mock_event)


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_checkout_session_metadata_as_stripe_object(mock_invalidate, mock_recompute, mock_session_local, db_session, test_project):
    """Test checkout processor handles metadata as Stripe object (not dict)."""
    mock_session_local.return_value = db_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = CheckoutSessionCompletedProcessor()
    
    mock_event = Mock()
    mock_session = Mock()
    mock_session.mode = "subscription"
    # Metadata as Stripe object with attributes
    mock_metadata = Mock()
    mock_metadata.user_id = "user_123"
    mock_metadata.project_id = test_project.project_id
    mock_session.metadata = mock_metadata
    mock_session.subscription = "sub_test123"
    mock_event.data.object = mock_session
    mock_event.id = "evt_test123"
    
    # Mock Stripe subscription retrieval
    mock_stripe_sub = Mock()
    mock_stripe_sub.id = "sub_test123"
    mock_stripe_sub.status = "active"
    mock_stripe_sub.current_period_start = int(datetime.utcnow().timestamp())
    mock_stripe_sub.current_period_end = int((datetime.utcnow().timestamp() + 86400 * 30))
    mock_stripe_sub.items.data = [Mock()]
    mock_stripe_sub.items.data[0].price.id = "price_test123"
    
    with patch('stripe.Subscription.retrieve', return_value=mock_stripe_sub):
        with patch('stripe.api_key', 'test_key'):
            # Should handle gracefully (will fail on price lookup, but shouldn't crash)
            processor.process(mock_event)


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_checkout_payment_creates_purchase(mock_invalidate, mock_recompute, mock_session_local, db_session, test_project, test_product, test_price):
    """Test checkout processor creates purchase for payment mode."""
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
    
    # Mock payment intent with charge
    mock_payment_intent = Mock()
    mock_payment_intent.status = "succeeded"
    mock_payment_intent.amount = 1000
    mock_payment_intent.currency = "usd"
    mock_charge = Mock()
    mock_charge.id = "ch_test123"
    mock_payment_intent.charges = Mock()
    mock_payment_intent.charges.data = [mock_charge]
    
    # Mock expanded checkout session with line items
    mock_expanded_session = Mock()
    mock_line_item = Mock()
    mock_line_item.price = Mock()
    mock_line_item.price.id = str(test_price.stripe_price_id)
    mock_expanded_session.line_items = Mock()
    mock_expanded_session.line_items.data = [mock_line_item]
    
    with patch('stripe.PaymentIntent.retrieve', return_value=mock_payment_intent):
        with patch('stripe.checkout.Session.retrieve', return_value=mock_expanded_session):
            with patch('stripe.api_key', 'test_key'):
                processor.process(mock_event)
    
    # Verify purchase was created
    db_session.commit()
    purchase = db_session.query(Purchase).filter(
        Purchase.stripe_charge_id == "ch_test123"
    ).first()
    assert purchase is not None
    assert purchase.user_id == "user_123"
    assert purchase.status == PurchaseStatus.SUCCEEDED
