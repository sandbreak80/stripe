"""Tests for webhook endpoint."""

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
def test_stripe_webhook_success(mock_get_payload, mock_get_signature, mock_verify, client, mock_event):
    """Test successful webhook processing."""
    # Setup mocks
    mock_get_signature.return_value = "test_signature"
    mock_get_payload.return_value = b'{"id":"evt_test123","type":"checkout.session.completed"}'
    mock_verify.return_value = mock_event
    
    # Mock event router
    with patch.object(event_router, 'process_event') as mock_process:
        response = client.post(
            "/api/v1/webhooks/stripe",
            headers={"Stripe-Signature": "test_signature"},
            content=b'{"id":"evt_test123","type":"checkout.session.completed"}',
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["received"] is True
        assert data["event_id"] == "evt_test123"
        mock_process.assert_called_once_with(mock_event)


@patch("billing_service.webhooks.verify_stripe_signature")
@patch("billing_service.webhooks.get_webhook_signature")
@patch("billing_service.webhooks.get_webhook_payload")
def test_stripe_webhook_invalid_signature(mock_get_payload, mock_get_signature, mock_verify, client):
    """Test webhook with invalid signature."""
    # Setup mocks
    mock_get_signature.return_value = "test_signature"
    mock_get_payload.return_value = b'{"id":"evt_test123"}'
    mock_verify.return_value = None  # Signature verification failed
    
    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": "invalid_signature"},
        content=b'{"id":"evt_test123"}',
    )
    
    assert response.status_code == 400
    data = response.json()
    assert "Failed to verify webhook signature" in data["detail"]


@patch("billing_service.webhooks.verify_stripe_signature")
@patch("billing_service.webhooks.get_webhook_signature")
@patch("billing_service.webhooks.get_webhook_payload")
@patch("billing_service.webhooks.event_router")
@patch("billing_service.cache.mark_event_processed")
def test_stripe_webhook_permanent_error(mock_mark, mock_router, mock_get_payload, mock_get_signature, mock_verify, client, mock_event):
    """Test webhook with permanent error (ValueError)."""
    # Setup mocks
    mock_get_signature.return_value = "test_signature"
    mock_get_payload.return_value = b'{"id":"evt_test123"}'
    mock_verify.return_value = mock_event
    
    # Simulate permanent error
    mock_router.process_event.side_effect = ValueError("Invalid data")
    
    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": "test_signature"},
        content=b'{"id":"evt_test123"}',
    )
    
    # Should return 200 OK for permanent errors (to prevent retry storms)
    assert response.status_code == 200
    data = response.json()
    assert data["received"] is True
    assert "error" in data
    mock_mark.assert_called_once_with(mock_event.id)


@patch("billing_service.webhooks.verify_stripe_signature")
@patch("billing_service.webhooks.get_webhook_signature")
@patch("billing_service.webhooks.get_webhook_payload")
@patch("billing_service.webhooks.event_router")
def test_stripe_webhook_transient_error(mock_router, mock_get_payload, mock_get_signature, mock_verify, client, mock_event):
    """Test webhook with transient error (Exception)."""
    # Setup mocks
    mock_get_signature.return_value = "test_signature"
    mock_get_payload.return_value = b'{"id":"evt_test123"}'
    mock_verify.return_value = mock_event
    
    # Simulate transient error
    mock_router.process_event.side_effect = Exception("Database connection failed")
    
    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"Stripe-Signature": "test_signature"},
        content=b'{"id":"evt_test123"}',
    )
    
    # Should return 500 for transient errors (to trigger Stripe retry)
    assert response.status_code == 500
    data = response.json()
    assert "Error processing event" in data["detail"]
