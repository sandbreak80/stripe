"""Stripe service for customer, checkout, and portal operations."""

import stripe
from sqlalchemy.orm import Session

from billing_service.config import settings
from billing_service.models import StripeCustomer, User

# Initialize Stripe
stripe.api_key = settings.stripe_secret_key


def get_or_create_stripe_customer(
    db: Session, user: User, email: str | None = None
) -> StripeCustomer:
    """Get or create a Stripe customer for a user."""
    # Check if customer already exists
    stripe_customer = db.query(StripeCustomer).filter(StripeCustomer.user_id == user.id).first()

    if stripe_customer:
        return stripe_customer

    # Create customer in Stripe
    customer_data: dict[str, str | dict[str, str]] = {
        "metadata": {"user_id": str(user.id), "project_id": str(user.project_id)}
    }
    if email:
        customer_data["email"] = email

    stripe_customer_obj = stripe.Customer.create(**customer_data)  # type: ignore[arg-type]

    # Create database record
    stripe_customer = StripeCustomer(
        user_id=user.id,
        stripe_customer_id=stripe_customer_obj.id,
    )
    db.add(stripe_customer)
    db.commit()
    db.refresh(stripe_customer)

    return stripe_customer


def create_checkout_session(
    db: Session,
    stripe_customer_id: str,
    price_id: str,
    mode: str,
    success_url: str,
    cancel_url: str,
    project_id: int,
) -> str:
    """Create a Stripe checkout session."""
    session = stripe.checkout.Session.create(
        customer=stripe_customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        mode=mode,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"project_id": str(project_id)},
    )
    if not session.url:
        raise ValueError("Stripe checkout session URL is None")
    return str(session.url)


def create_portal_session(stripe_customer_id: str, return_url: str) -> str:
    """Create a Stripe customer portal session."""
    session = stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=return_url,
    )
    if not session.url:
        raise ValueError("Stripe portal session URL is None")
    return str(session.url)
