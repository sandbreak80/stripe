"""Webhook signature verification."""

import hashlib
import hmac

from fastapi import Request


def verify_stripe_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Stripe webhook signature."""
    try:
        # Stripe sends signature in format: t=timestamp,v1=signature
        # We need to extract the signature part
        elements = signature.split(",")
        sig_header = None
        timestamp = None

        for element in elements:
            if element.startswith("v1="):
                sig_header = element.split("=", 1)[1]
            elif element.startswith("t="):
                timestamp = element.split("=", 1)[1]

        if not sig_header or not timestamp:
            return False

        # Create the signed payload
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"

        # Compute the expected signature
        expected_sig = hmac.new(
            secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_sig, sig_header)
    except Exception:
        return False


def get_stripe_signature(request: Request) -> str | None:
    """Extract Stripe signature from request headers."""
    return request.headers.get("stripe-signature")
