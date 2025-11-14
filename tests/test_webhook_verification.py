"""Tests for webhook verification."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from billing_service.webhook_verification import verify_stripe_signature


@patch("billing_service.webhook_verification.settings")
@patch("billing_service.webhook_verification.stripe.Webhook.construct_event")
def test_verify_stripe_signature_success(mock_construct, mock_settings):
    """Test successful webhook signature verification."""
    mock_settings.stripe_webhook_secret = "whsec_test"
    mock_event = Mock()
    mock_construct.return_value = mock_event

    payload = b'{"type": "checkout.session.completed"}'
    signature = "test_signature"

    result = verify_stripe_signature(payload, signature)

    assert result == mock_event
    mock_construct.assert_called_once_with(payload, signature, "whsec_test")


@patch("billing_service.webhook_verification.settings")
@patch("billing_service.webhook_verification.stripe.Webhook.construct_event")
def test_verify_stripe_signature_failure(mock_construct, mock_settings):
    """Test failed webhook signature verification."""
    import stripe
    from fastapi import HTTPException

    mock_settings.stripe_webhook_secret = "whsec_test"
    mock_construct.side_effect = stripe.SignatureVerificationError("Invalid signature", "sig")

    payload = b'{"type": "checkout.session.completed"}'
    signature = "invalid_signature"

    with pytest.raises(HTTPException) as exc_info:
        verify_stripe_signature(payload, signature)

    assert exc_info.value.status_code == 401


@patch("billing_service.webhook_verification.settings")
def test_verify_stripe_signature_missing_secret(mock_settings):
    """Test webhook verification when secret is not configured."""
    from fastapi import HTTPException

    mock_settings.stripe_webhook_secret = None

    payload = b'{"type": "checkout.session.completed"}'
    signature = "test_signature"

    with pytest.raises(HTTPException) as exc_info:
        verify_stripe_signature(payload, signature)

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_get_webhook_signature():
    """Test extracting webhook signature from headers."""
    from fastapi import Request
    from billing_service.webhook_verification import get_webhook_signature

    mock_request = Mock(spec=Request)
    mock_request.headers = {"Stripe-Signature": "test_sig_123"}

    signature = await get_webhook_signature(mock_request)
    assert signature == "test_sig_123"


@pytest.mark.asyncio
async def test_get_webhook_signature_missing():
    """Test extracting webhook signature when header is missing."""
    from fastapi import Request, HTTPException
    from billing_service.webhook_verification import get_webhook_signature

    mock_request = Mock(spec=Request)
    mock_request.headers = {}

    with pytest.raises(HTTPException) as exc_info:
        await get_webhook_signature(mock_request)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_webhook_payload():
    """Test extracting webhook payload."""
    from fastapi import Request
    from billing_service.webhook_verification import get_webhook_payload

    mock_request = Mock(spec=Request)
    mock_request.body = AsyncMock(return_value=b'{"type": "test"}')

    payload = await get_webhook_payload(mock_request)
    assert payload == b'{"type": "test"}'
