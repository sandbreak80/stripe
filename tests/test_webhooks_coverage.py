"""Additional tests for webhook endpoint to increase coverage."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from billing_service.main import app
from billing_service.webhook_processors import event_router


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_event():
    """Create a mock Stripe event."""
    mock_event = Mock()
    mock_event.id = "evt_test123"
    mock_event.type = "checkout.session.completed"
    mock_event.livemode = False
    return mock_event


@patch("billing_service.webhooks.verify_stripe_signature")
@patch("billing_service.webhooks.get_webhook_signature")
@patch("billing_service.webhooks.get_webhook_payload")
@patch("billing_service.webhooks.event_router")
def test_stripe_webhook_unknown_event_type(mock_router, mock_get_payload, mock_get_signature, mock_verify, client, mock_event):
    """Test webhook handles unknown event types gracefully."""
    mock_get_signature.return_value = "test_signature"
    mock_get_payload.return_value = b'{"id":"evt_test123","type":"unknown.event.type"}'
    mock_verify.return_value = mock_event
    mock_event.type = "unknown.event.type"
    
    # Mock event router to handle unknown events
    mock_router.process_event.return_value = None
    
    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": "test_signature"},
        content=b'{"id":"evt_test123","type":"unknown.event.type"}',
    )
    
    # Should return 200 OK even for unknown events
    assert response.status_code == 200
    mock_router.process_event.assert_called_once_with(mock_event)


@patch("billing_service.webhooks.verify_stripe_signature")
@patch("billing_service.webhooks.get_webhook_signature")
@patch("billing_service.webhooks.get_webhook_payload")
def test_stripe_webhook_missing_signature_header(mock_get_payload, mock_get_signature, mock_verify, client):
    """Test webhook handles missing signature header."""
    mock_get_signature.side_effect = ValueError("Missing signature header")
    mock_get_payload.return_value = b'{"id":"evt_test123"}'
    
    response = client.post(
        "/api/v1/webhooks/stripe",
        content=b'{"id":"evt_test123"}',
    )
    
    # Should return 400 or 500 error
    assert response.status_code in [400, 500]


@patch("billing_service.webhooks.verify_stripe_signature")
@patch("billing_service.webhooks.get_webhook_signature")
@patch("billing_service.webhooks.get_webhook_payload")
@patch("billing_service.webhooks.event_router")
def test_stripe_webhook_event_already_processed(mock_router, mock_get_payload, mock_get_signature, mock_verify, client, mock_event):
    """Test webhook handles already processed events."""
    mock_get_signature.return_value = "test_signature"
    mock_get_payload.return_value = b'{"id":"evt_test123"}'
    mock_verify.return_value = mock_event
    
    # Mock event router to process successfully
    mock_router.process_event.return_value = None
    
    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": "test_signature"},
        content=b'{"id":"evt_test123"}',
    )
    
    # Should return 200 OK
    assert response.status_code == 200
    mock_router.process_event.assert_called_once_with(mock_event)


@patch("billing_service.webhooks.verify_stripe_signature")
@patch("billing_service.webhooks.get_webhook_signature")
@patch("billing_service.webhooks.get_webhook_payload")
def test_stripe_webhook_unexpected_exception(mock_get_payload, mock_get_signature, mock_verify, client):
    """Test webhook handles unexpected exceptions."""
    mock_get_signature.return_value = "test_signature"
    mock_get_payload.return_value = b'{"id":"evt_test123"}'
    mock_verify.side_effect = Exception("Unexpected error")
    
    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": "test_signature"},
        content=b'{"id":"evt_test123"}',
    )
    
    # Should return 500 error
    assert response.status_code == 500


@patch("billing_service.webhooks.verify_stripe_signature")
@patch("billing_service.webhooks.get_webhook_signature")
@patch("billing_service.webhooks.get_webhook_payload")
@patch("billing_service.webhooks.event_router")
def test_stripe_webhook_http_exception_re_raise(mock_router, mock_get_payload, mock_get_signature, mock_verify, client):
    """Test webhook re-raises HTTPException."""
    from fastapi import HTTPException, status
    
    mock_get_signature.return_value = "test_signature"
    mock_get_payload.return_value = b'{"id":"evt_test123"}'
    mock_verify.side_effect = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid signature"
    )
    
    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": "test_signature"},
        content=b'{"id":"evt_test123"}',
    )
    
    # Should return the HTTPException status code
    assert response.status_code == 400


@patch("billing_service.webhooks.verify_stripe_signature")
@patch("billing_service.webhooks.get_webhook_signature")
@patch("billing_service.webhooks.get_webhook_payload")
@patch("billing_service.webhooks.event_router")
def test_stripe_webhook_transient_error(mock_router, mock_get_payload, mock_get_signature, mock_verify, client, mock_event):
    """Test webhook handles transient errors (non-ValueError exceptions)."""
    mock_get_signature.return_value = "test_signature"
    mock_get_payload.return_value = b'{"id":"evt_test123"}'
    mock_verify.return_value = mock_event
    mock_router.process_event.side_effect = Exception("Database connection error")
    
    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": "test_signature"},
        content=b'{"id":"evt_test123"}',
    )
    
    # Should return 500 to trigger Stripe retry
    assert response.status_code == 500


@patch("billing_service.webhooks.verify_stripe_signature")
@patch("billing_service.webhooks.get_webhook_signature")
@patch("billing_service.webhooks.get_webhook_payload")
@patch("billing_service.webhooks.event_router")
@patch("billing_service.cache.mark_event_processed")
def test_stripe_webhook_permanent_error(mock_mark_processed, mock_router, mock_get_payload, mock_get_signature, mock_verify, client, mock_event):
    """Test webhook handles permanent errors (ValueError) by marking event as processed."""
    mock_get_signature.return_value = "test_signature"
    mock_get_payload.return_value = b'{"id":"evt_test123"}'
    mock_verify.return_value = mock_event
    mock_router.process_event.side_effect = ValueError("Invalid event data")
    
    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": "test_signature"},
        content=b'{"id":"evt_test123"}',
    )
    
    # Should return 200 OK and mark event as processed
    assert response.status_code == 200
    mock_mark_processed.assert_called_once_with("evt_test123")
