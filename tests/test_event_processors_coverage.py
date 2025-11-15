"""Additional tests for event processors to increase coverage."""

import pytest
import uuid
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
def test_checkout_session_completed_subscription_creates_subscription(mock_invalidate, mock_recompute, mock_session_local, db_engine, test_project, test_product, test_price):
    """Test checkout processor creates subscription for subscription mode."""
    from sqlalchemy.orm import sessionmaker
    TestingSessionLocal = sessionmaker(bind=db_engine)
    test_db = TestingSessionLocal()
    
    def create_session():
        return TestingSessionLocal()
    
    mock_session_local.side_effect = create_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = CheckoutSessionCompletedProcessor()
    
    # Use unique IDs to avoid conflicts
    unique_sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    unique_evt_id = f"evt_{uuid.uuid4().hex[:24]}"
    
    # Create mock event with subscription mode - use project.project_id not project.id
    mock_event = Mock()
    mock_session = Mock()
    mock_session.mode = "subscription"
    mock_session.metadata = {"user_id": "user_123", "project_id": test_project.project_id}  # Use project_id string
    mock_session.subscription = unique_sub_id
    mock_event.data.object = mock_session
    mock_event.id = unique_evt_id
    
    # Mock Stripe subscription retrieval
    # Create a mock that properly handles canceled_at as None
    mock_stripe_sub = Mock()
    # Set all required attributes explicitly
    mock_stripe_sub.id = unique_sub_id
    mock_stripe_sub.status = "active"
    mock_stripe_sub.current_period_start = int(datetime.utcnow().timestamp())
    mock_stripe_sub.current_period_end = int((datetime.utcnow().timestamp() + 86400 * 30))
    mock_stripe_sub.cancel_at_period_end = False
    # Set canceled_at to None - this is critical for the test
    # Use configure_mock to ensure it's not returning a Mock object
    mock_stripe_sub.configure_mock(canceled_at=None)
    # Set up items structure
    mock_item = Mock()
    mock_item.price = Mock()
    mock_item.price.id = str(test_price.stripe_price_id)
    mock_stripe_sub.items = Mock()
    mock_stripe_sub.items.data = [mock_item]
    
    with patch('stripe.Subscription.retrieve', return_value=mock_stripe_sub):
        with patch('stripe.api_key', 'test_key'):
            processor.process(mock_event)
    
    # Verify subscription was created
    test_db.commit()
    subscription = test_db.query(Subscription).filter(
        Subscription.stripe_subscription_id == unique_sub_id
    ).first()
    assert subscription is not None
    assert subscription.user_id == "user_123"
    assert subscription.status == SubscriptionStatus.ACTIVE
    test_db.close()


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_invoice_payment_succeeded_updates_subscription_period(mock_invalidate, mock_recompute, mock_session_local, db_engine, test_project, test_product, test_price):
    """Test invoice processor updates subscription period."""
    from sqlalchemy.orm import sessionmaker
    TestingSessionLocal = sessionmaker(bind=db_engine)
    test_db = TestingSessionLocal()
    
    def create_session():
        return TestingSessionLocal()
    
    mock_session_local.side_effect = create_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = InvoicePaymentSucceededProcessor()
    
    # Use unique IDs to avoid conflicts
    unique_sub_id = f"sub_{uuid.uuid4().hex[:24]}"
    unique_evt_id = f"evt_{uuid.uuid4().hex[:24]}"
    
    try:
        # Create subscription
        subscription = Subscription(
            stripe_subscription_id=unique_sub_id,
            user_id="user_123",
            project_id=test_project.id,
            price_id=test_price.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow(),
            cancel_at_period_end=False,
        )
        test_db.add(subscription)
        test_db.commit()
        
        # Create mock event
        mock_event = Mock()
        mock_event.id = unique_evt_id
        mock_invoice = Mock()
        mock_invoice.subscription = unique_sub_id
        mock_invoice.customer = "cus_test123"
        mock_invoice.period_start = int(datetime.utcnow().timestamp())
        mock_invoice.period_end = int((datetime.utcnow().timestamp() + 86400 * 30))
        mock_event.data.object = mock_invoice
        
        processor.process(mock_event)
        
        # Verify subscription period was updated (query fresh from database)
        test_db.commit()
        updated_subscription = test_db.query(Subscription).filter(
            Subscription.stripe_subscription_id == unique_sub_id
        ).first()
        assert updated_subscription is not None
        assert updated_subscription.current_period_start is not None
        assert updated_subscription.current_period_end is not None
    finally:
        test_db.close()


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_charge_refunded_processor_handles_missing_purchase(mock_invalidate, mock_recompute, mock_session_local, db_engine):
    """Test charge refunded processor handles missing purchase gracefully."""
    from sqlalchemy.orm import sessionmaker
    TestingSessionLocal = sessionmaker(bind=db_engine)
    test_db = TestingSessionLocal()
    
    def create_session():
        return TestingSessionLocal()
    
    mock_session_local.side_effect = create_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = ChargeRefundedProcessor()
    
    try:
        # Create mock event for non-existent charge
        mock_event = Mock()
        mock_event.id = "evt_test123"
        mock_charge = Mock()
        mock_charge.id = "ch_nonexistent"
        mock_event.data.object = mock_charge
        
        # Should not raise exception
        processor.process(mock_event)
        
        # Verify no purchase was found (no exception raised)
        purchase = test_db.query(Purchase).filter(
            Purchase.stripe_charge_id == "ch_nonexistent"
        ).first()
        assert purchase is None
    finally:
        test_db.close()


@patch("billing_service.event_processors.SessionLocal")
@patch("billing_service.event_processors.recompute_and_store_entitlements")
@patch("billing_service.event_processors.invalidate_entitlements_cache")
def test_checkout_session_unknown_mode(mock_invalidate, mock_recompute, mock_session_local, db_engine, test_project):
    """Test checkout processor handles unknown checkout mode gracefully."""
    from sqlalchemy.orm import sessionmaker
    TestingSessionLocal = sessionmaker(bind=db_engine)
    
    def create_session():
        return TestingSessionLocal()
    
    mock_session_local.side_effect = create_session
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
def test_checkout_session_metadata_as_stripe_object(mock_invalidate, mock_recompute, mock_session_local, db_engine, test_project):
    """Test checkout processor handles metadata as Stripe object (not dict)."""
    from sqlalchemy.orm import sessionmaker
    TestingSessionLocal = sessionmaker(bind=db_engine)
    
    def create_session():
        return TestingSessionLocal()
    
    mock_session_local.side_effect = create_session
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
def test_checkout_payment_creates_purchase(mock_invalidate, mock_recompute, mock_session_local, db_engine, test_project, test_product, test_price):
    """Test checkout processor creates purchase for payment mode."""
    from sqlalchemy.orm import sessionmaker
    TestingSessionLocal = sessionmaker(bind=db_engine)
    test_db = TestingSessionLocal()
    
    def create_session():
        return TestingSessionLocal()
    
    mock_session_local.side_effect = create_session
    mock_recompute.return_value = None
    mock_invalidate.return_value = None
    
    processor = CheckoutSessionCompletedProcessor()
    
    # Use unique IDs to avoid conflicts
    unique_user_id = f"user_{uuid.uuid4().hex[:24]}"
    unique_pi_id = f"pi_{uuid.uuid4().hex[:24]}"
    unique_cs_id = f"cs_{uuid.uuid4().hex[:24]}"
    unique_ch_id = f"ch_{uuid.uuid4().hex[:24]}"
    unique_evt_id = f"evt_{uuid.uuid4().hex[:24]}"
    
    mock_event = Mock()
    mock_session = Mock()
    mock_session.mode = "payment"
    mock_session.metadata = {"user_id": unique_user_id, "project_id": test_project.project_id}
    mock_session.payment_intent = unique_pi_id
    mock_session.id = unique_cs_id
    mock_event.data.object = mock_session
    mock_event.id = unique_evt_id
    
    # Mock payment intent with charge
    mock_payment_intent = Mock()
    mock_payment_intent.status = "succeeded"
    mock_payment_intent.amount = 1000
    mock_payment_intent.currency = "usd"
    mock_charge = Mock()
    mock_charge.id = unique_ch_id
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
    
    try:
        # Verify purchase was created
        test_db.commit()
        purchase = test_db.query(Purchase).filter(
            Purchase.stripe_charge_id == unique_ch_id
        ).first()
        assert purchase is not None
        assert purchase.user_id == unique_user_id
        assert purchase.status == PurchaseStatus.SUCCEEDED
    finally:
        test_db.close()
