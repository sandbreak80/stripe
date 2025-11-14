"""Tests for event processors."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from billing_service.event_processors import (
    CheckoutSessionCompletedProcessor,
    InvoicePaymentSucceededProcessor,
    CustomerSubscriptionUpdatedProcessor,
    CustomerSubscriptionDeletedProcessor,
    ChargeRefundedProcessor,
)
from billing_service.models import (
    Project,
    Subscription,
    Purchase,
    SubscriptionStatus,
    PurchaseStatus,
    Price,
    Product,
    PriceInterval,
)


def test_checkout_session_completed_processor_get_event_type():
    """Test processor get_event_type method."""
    processor = CheckoutSessionCompletedProcessor()
    assert processor.get_event_type() == "checkout.session.completed"


def test_invoice_payment_succeeded_processor_get_event_type():
    """Test processor get_event_type method."""
    processor = InvoicePaymentSucceededProcessor()
    assert processor.get_event_type() == "invoice.payment_succeeded"


def test_customer_subscription_updated_processor_get_event_type():
    """Test processor get_event_type method."""
    processor = CustomerSubscriptionUpdatedProcessor()
    assert processor.get_event_type() == "customer.subscription.updated"


def test_customer_subscription_deleted_processor_get_event_type():
    """Test processor get_event_type method."""
    processor = CustomerSubscriptionDeletedProcessor()
    assert processor.get_event_type() == "customer.subscription.deleted"


def test_charge_refunded_processor_get_event_type():
    """Test processor get_event_type method."""
    processor = ChargeRefundedProcessor()
    assert processor.get_event_type() == "charge.refunded"


def test_event_router_registers_processor():
    """Test event router registration."""
    from billing_service.webhook_processors import EventRouter

    router = EventRouter()
    processor = CheckoutSessionCompletedProcessor()
    router.register_processor(processor)

    assert "checkout.session.completed" in router._processors
    assert router._processors["checkout.session.completed"] == processor


def test_event_router_processes_event():
    """Test event router processes event."""
    from billing_service.webhook_processors import EventRouter

    router = EventRouter()
    processor = Mock()
    processor.get_event_type.return_value = "test.event"
    processor.process = Mock()

    router.register_processor(processor)

    mock_event = Mock()
    mock_event.type = "test.event"
    mock_event.id = "evt_test123"

    with patch("billing_service.webhook_processors.is_event_processed", return_value=False):
        with patch("billing_service.webhook_processors.mark_event_processed"):
            router.process_event(mock_event)

    processor.process.assert_called_once_with(mock_event)


def test_event_router_skips_processed_event():
    """Test event router skips already processed events."""
    from billing_service.webhook_processors import EventRouter

    router = EventRouter()
    processor = Mock()
    processor.get_event_type.return_value = "test.event"
    processor.process = Mock()

    router.register_processor(processor)

    mock_event = Mock()
    mock_event.type = "test.event"
    mock_event.id = "evt_test123"

    with patch("billing_service.webhook_processors.is_event_processed", return_value=True):
        router.process_event(mock_event)

    processor.process.assert_not_called()


def test_event_router_handles_unknown_event():
    """Test event router handles unknown event types."""
    from billing_service.webhook_processors import EventRouter

    router = EventRouter()

    mock_event = Mock()
    mock_event.type = "unknown.event"
    mock_event.id = "evt_test123"

    with patch("billing_service.webhook_processors.is_event_processed", return_value=False):
        with patch("billing_service.webhook_processors.mark_event_processed") as mock_mark:
            router.process_event(mock_event)

    # Should mark as processed even if no processor
    mock_mark.assert_called_once_with("evt_test123")
