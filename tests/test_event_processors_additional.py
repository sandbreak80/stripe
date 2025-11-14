"""Additional tests for event processors."""

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


def test_event_processor_base_methods():
    """Test that all processors implement required methods."""
    processors = [
        CheckoutSessionCompletedProcessor(),
        InvoicePaymentSucceededProcessor(),
        CustomerSubscriptionUpdatedProcessor(),
        CustomerSubscriptionDeletedProcessor(),
        ChargeRefundedProcessor(),
    ]
    
    for processor in processors:
        # Should have get_event_type method
        assert hasattr(processor, 'get_event_type')
        assert callable(processor.get_event_type)
        event_type = processor.get_event_type()
        assert isinstance(event_type, str)
        assert len(event_type) > 0
        
        # Should have process method
        assert hasattr(processor, 'process')
        assert callable(processor.process)


def test_event_processor_unique_event_types():
    """Test that each processor handles a unique event type."""
    processors = [
        CheckoutSessionCompletedProcessor(),
        InvoicePaymentSucceededProcessor(),
        CustomerSubscriptionUpdatedProcessor(),
        CustomerSubscriptionDeletedProcessor(),
        ChargeRefundedProcessor(),
    ]
    
    event_types = [p.get_event_type() for p in processors]
    
    # All event types should be unique
    assert len(event_types) == len(set(event_types))


def test_event_router_error_handling():
    """Test event router handles processing errors."""
    from billing_service.webhook_processors import EventRouter
    
    router = EventRouter()
    
    # Create a processor that raises an error
    error_processor = Mock()
    error_processor.get_event_type.return_value = "test.error"
    error_processor.process.side_effect = Exception("Processing error")
    
    router.register_processor(error_processor)
    
    mock_event = Mock()
    mock_event.type = "test.error"
    mock_event.id = "evt_error123"
    
    with patch("billing_service.webhook_processors.is_event_processed", return_value=False):
        # Should raise exception, not mark as processed
        # The processor raises Exception, which the router propagates
        with pytest.raises(Exception, match="Processing error"):  # noqa: B017
            router.process_event(mock_event)


def test_event_router_logs_warnings():
    """Test event router logs warnings for unknown events."""
    from billing_service.webhook_processors import EventRouter
    import logging
    
    router = EventRouter()
    
    mock_event = Mock()
    mock_event.type = "unknown.event.type"
    mock_event.id = "evt_unknown123"
    
    with patch("billing_service.webhook_processors.is_event_processed", return_value=False):
        with patch("billing_service.webhook_processors.mark_event_processed") as mock_mark:
            with patch("billing_service.webhook_processors.logger") as mock_logger:
                router.process_event(mock_event)
                
                # Should log warning
                mock_logger.warning.assert_called()
                # Should still mark as processed
                mock_mark.assert_called_once_with("evt_unknown123")
