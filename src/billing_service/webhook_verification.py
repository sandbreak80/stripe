"""Stripe webhook signature verification."""


import stripe
from fastapi import HTTPException, Request, status

from billing_service.config import settings


def verify_stripe_signature(
    payload: bytes,
    signature: str,
) -> stripe.Event | None:
    """
    Verify Stripe webhook signature and construct event.

    Args:
        payload: Raw request body as bytes
        signature: Stripe-Signature header value

    Returns:
        Stripe Event object if signature is valid, None otherwise

    Raises:
        HTTPException: If signature verification fails
    """
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured",
        )

    try:
        event = stripe.Webhook.construct_event(
            payload,
            signature,
            settings.stripe_webhook_secret,
        )
        return event
    except ValueError as e:
        # Invalid payload
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid payload: {str(e)}",
        ) from e
    except stripe.SignatureVerificationError as e:  # type: ignore
        # Invalid signature
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid signature: {str(e)}",
        ) from e
    except Exception as e:
        # Other errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook verification error: {str(e)}",
        ) from e


async def get_webhook_signature(request: Request) -> str:
    """Extract Stripe-Signature header from request."""
    signature = request.headers.get("Stripe-Signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Stripe-Signature header",
        )
    return signature


async def get_webhook_payload(request: Request) -> bytes:
    """Get raw request body as bytes for signature verification."""
    return await request.body()
