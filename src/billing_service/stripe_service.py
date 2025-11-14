"""Stripe service integration."""

from typing import Literal

import stripe

from billing_service.config import settings

# Initialize Stripe
stripe.api_key = settings.stripe_secret_key


def create_checkout_session(
    price_stripe_id: str,
    user_id: str,
    project_id: str,
    mode: Literal["subscription", "payment"],
    success_url: str,
    cancel_url: str,
) -> stripe.checkout.Session:
    """Create a Stripe checkout session."""
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[
            {
                "price": price_stripe_id,
                "quantity": 1,
            }
        ],
        mode=mode,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "user_id": user_id,
            "project_id": project_id,
        },
    )
    return session


def create_portal_session(
    customer_id: str,
    return_url: str,
) -> stripe.billing_portal.Session:
    """Create a Stripe Customer Portal session."""
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session


def get_price(stripe_price_id: str) -> stripe.Price | None:
    """Retrieve a Stripe price."""
    try:
        return stripe.Price.retrieve(stripe_price_id)
    except stripe.StripeError:
        return None
