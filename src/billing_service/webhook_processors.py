"""Webhook event processors for Stripe events."""

from collections.abc import Callable
from datetime import datetime
from typing import Any

import stripe
from sqlalchemy.orm import Session

from billing_service.cache import invalidate_entitlements_cache
from billing_service.config import settings
from billing_service.entitlements import recompute_and_store_entitlements
from billing_service.models import Purchase, Subscription

# Initialize Stripe
stripe.api_key = settings.stripe_secret_key


def process_checkout_session_completed(event_data: dict[str, Any], db: Session) -> None:
    """Process checkout.session.completed event."""
    session = event_data.get("data", {}).get("object", {})
    customer_id = session.get("customer")
    metadata = session.get("metadata", {})
    project_id = metadata.get("project_id")

    if not customer_id or not project_id:
        return

    # Find user by Stripe customer
    from billing_service.models import StripeCustomer

    stripe_customer = (
        db.query(StripeCustomer).filter(StripeCustomer.stripe_customer_id == customer_id).first()
    )

    if not stripe_customer:
        return

    # Handle subscription vs one-time payment
    mode = session.get("mode")
    if mode == "subscription":
        subscription_id = session.get("subscription")
        if subscription_id:
            # Subscription will be handled by subscription.created event
            pass
    elif mode == "payment":
        payment_intent_id = session.get("payment_intent")
        if payment_intent_id:
            # Purchase will be handled by payment_intent.succeeded event
            pass


def process_payment_intent_succeeded(event_data: dict[str, Any], db: Session) -> None:
    """Process payment_intent.succeeded event."""
    payment_intent = event_data.get("data", {}).get("object", {})
    payment_intent_id = payment_intent.get("id")
    customer_id = payment_intent.get("customer")
    amount = payment_intent.get("amount")
    currency = payment_intent.get("currency", "usd")

    if not payment_intent_id or not customer_id:
        return

    # Find user by Stripe customer
    from billing_service.models import StripeCustomer

    stripe_customer = (
        db.query(StripeCustomer).filter(StripeCustomer.stripe_customer_id == customer_id).first()
    )

    if not stripe_customer:
        return

    user = stripe_customer.user

    # Check if purchase already exists (idempotency)
    existing_purchase = (
        db.query(Purchase).filter(Purchase.stripe_payment_intent_id == payment_intent_id).first()
    )

    if existing_purchase:
        # Already processed, update status if needed
        if existing_purchase.status != "succeeded":
            existing_purchase.status = "succeeded"  # type: ignore[assignment]
            existing_purchase.updated_at = datetime.utcnow()  # type: ignore[assignment]
            db.commit()
        return

    # Get price ID from metadata or line items
    price_id = None
    metadata = payment_intent.get("metadata", {})
    if "price_id" in metadata:
        price_id = metadata["price_id"]
    else:
        # Try to get from invoice or subscription
        invoice_id = payment_intent.get("invoice")
        if invoice_id:
            try:
                invoice = stripe.Invoice.retrieve(invoice_id)
                if invoice.lines and len(invoice.lines.data) > 0:
                    price = invoice.lines.data[0].price
                    if price and hasattr(price, "id"):
                        price_id = price.id
            except Exception:
                pass

    if not price_id:
        # Default price ID if not found
        price_id = "unknown"

    # Create purchase record
    purchase = Purchase(
        user_id=user.id,
        project_id=user.project_id,
        stripe_payment_intent_id=payment_intent_id,
        stripe_price_id=price_id,
        amount=amount or 0,
        currency=currency,
        status="succeeded",
    )
    db.add(purchase)
    db.commit()

    # Recompute entitlements and invalidate cache
    recompute_and_store_entitlements(user.id, user.project_id, db)
    invalidate_entitlements_cache(user.id, user.project_id)


def process_payment_intent_failed(event_data: dict[str, Any], db: Session) -> None:
    """Process payment_intent.payment_failed event."""
    payment_intent = event_data.get("data", {}).get("object", {})
    payment_intent_id = payment_intent.get("id")

    if not payment_intent_id:
        return

    # Update existing purchase status if it exists
    purchase = (
        db.query(Purchase).filter(Purchase.stripe_payment_intent_id == payment_intent_id).first()
    )

    if purchase:
        purchase.status = "failed"  # type: ignore[assignment]
        purchase.updated_at = datetime.utcnow()  # type: ignore[assignment]
        db.commit()

        # Recompute entitlements and invalidate cache
        recompute_and_store_entitlements(purchase.user_id, purchase.project_id, db)  # type: ignore[arg-type]
        invalidate_entitlements_cache(purchase.user_id, purchase.project_id)  # type: ignore[arg-type]


def process_subscription_created(event_data: dict[str, Any], db: Session) -> None:
    """Process customer.subscription.created event."""
    subscription_obj = event_data.get("data", {}).get("object", {})
    subscription_id = subscription_obj.get("id")
    customer_id = subscription_obj.get("customer")

    if not subscription_id or not customer_id:
        return

    # Find user by Stripe customer
    from billing_service.models import StripeCustomer

    stripe_customer = (
        db.query(StripeCustomer).filter(StripeCustomer.stripe_customer_id == customer_id).first()
    )

    if not stripe_customer:
        return

    user = stripe_customer.user

    # Check if subscription already exists (idempotency)
    existing_subscription = (
        db.query(Subscription)
        .filter(Subscription.stripe_subscription_id == subscription_id)
        .first()
    )

    if existing_subscription:
        # Already processed, update if needed
        return

    # Get price ID
    items = subscription_obj.get("items", {}).get("data", [])
    price_obj = items[0].get("price") if items else None
    price_id = price_obj.get("id") if price_obj and isinstance(price_obj, dict) else "unknown"

    # Get period dates
    current_period_start = subscription_obj.get("current_period_start")
    current_period_end = subscription_obj.get("current_period_end")

    # Create subscription record
    subscription = Subscription(
        user_id=user.id,
        project_id=user.project_id,
        stripe_subscription_id=subscription_id,
        stripe_price_id=price_id,
        status=subscription_obj.get("status", "active"),
        current_period_start=datetime.fromtimestamp(current_period_start)
        if current_period_start
        else None,
        current_period_end=datetime.fromtimestamp(current_period_end)
        if current_period_end
        else None,
        cancel_at_period_end=subscription_obj.get("cancel_at_period_end", False),
    )
    db.add(subscription)
    db.commit()

    # Recompute entitlements and invalidate cache
    recompute_and_store_entitlements(user.id, user.project_id, db)
    invalidate_entitlements_cache(user.id, user.project_id)


def process_subscription_updated(event_data: dict[str, Any], db: Session) -> None:
    """Process customer.subscription.updated event."""
    subscription_obj = event_data.get("data", {}).get("object", {})
    subscription_id = subscription_obj.get("id")

    if not subscription_id:
        return

    # Find existing subscription
    subscription = (
        db.query(Subscription)
        .filter(Subscription.stripe_subscription_id == subscription_id)
        .first()
    )

    if not subscription:
        # If not found, create it (might have been missed)
        process_subscription_created(event_data, db)
        return

    # Update subscription fields
    status_value = subscription_obj.get("status", subscription.status)
    subscription.status = status_value
    current_period_start = subscription_obj.get("current_period_start")
    current_period_end = subscription_obj.get("current_period_end")

    if current_period_start:
        subscription.current_period_start = datetime.fromtimestamp(current_period_start)  # type: ignore[assignment]
    if current_period_end:
        subscription.current_period_end = datetime.fromtimestamp(current_period_end)  # type: ignore[assignment]

    subscription.cancel_at_period_end = subscription_obj.get("cancel_at_period_end", False)
    subscription.updated_at = datetime.utcnow()  # type: ignore[assignment]
    db.commit()

    # Recompute entitlements and invalidate cache
    recompute_and_store_entitlements(subscription.user_id, subscription.project_id, db)  # type: ignore[arg-type]
    invalidate_entitlements_cache(subscription.user_id, subscription.project_id)  # type: ignore[arg-type]


def process_subscription_deleted(event_data: dict[str, Any], db: Session) -> None:
    """Process customer.subscription.deleted event."""
    subscription_obj = event_data.get("data", {}).get("object", {})
    subscription_id = subscription_obj.get("id")

    if not subscription_id:
        return

    # Find existing subscription
    subscription = (
        db.query(Subscription)
        .filter(Subscription.stripe_subscription_id == subscription_id)
        .first()
    )

    if not subscription:
        return

    # Update status to canceled (non-destructive)
    subscription.status = "canceled"  # type: ignore[assignment]
    subscription.updated_at = datetime.utcnow()  # type: ignore[assignment]
    db.commit()

    # Recompute entitlements and invalidate cache
    recompute_and_store_entitlements(subscription.user_id, subscription.project_id, db)  # type: ignore[arg-type]
    invalidate_entitlements_cache(subscription.user_id, subscription.project_id)  # type: ignore[arg-type]


def process_invoice_payment_succeeded(event_data: dict[str, Any], db: Session) -> None:
    """Process invoice.payment_succeeded event."""
    invoice = event_data.get("data", {}).get("object", {})
    subscription_id = invoice.get("subscription")

    if subscription_id:
        # Update subscription period if needed
        subscription = (
            db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == subscription_id)
            .first()
        )

        if subscription:
            period_start = invoice.get("period_start")
            period_end = invoice.get("period_end")

            if period_start:
                subscription.current_period_start = datetime.fromtimestamp(period_start)  # type: ignore[assignment]
            if period_end:
                subscription.current_period_end = datetime.fromtimestamp(period_end)  # type: ignore[assignment]

            subscription.status = "active"  # type: ignore[assignment]
            subscription.updated_at = datetime.utcnow()  # type: ignore[assignment]
            db.commit()

            # Recompute entitlements and invalidate cache
            recompute_and_store_entitlements(subscription.user_id, subscription.project_id, db)  # type: ignore[arg-type]
            invalidate_entitlements_cache(subscription.user_id, subscription.project_id)  # type: ignore[arg-type]


def process_invoice_payment_failed(event_data: dict[str, Any], db: Session) -> None:
    """Process invoice.payment_failed event."""
    invoice = event_data.get("data", {}).get("object", {})
    subscription_id = invoice.get("subscription")

    if subscription_id:
        subscription = (
            db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == subscription_id)
            .first()
        )

        if subscription:
            subscription.status = "past_due"  # type: ignore[assignment]
            subscription.updated_at = datetime.utcnow()  # type: ignore[assignment]
            db.commit()

            # Recompute entitlements and invalidate cache
            recompute_and_store_entitlements(subscription.user_id, subscription.project_id, db)  # type: ignore[arg-type]
            invalidate_entitlements_cache(subscription.user_id, subscription.project_id)  # type: ignore[arg-type]


def process_charge_refunded(event_data: dict[str, Any], db: Session) -> None:
    """Process charge.refunded event."""
    charge = event_data.get("data", {}).get("object", {})
    payment_intent_id = charge.get("payment_intent")

    if not payment_intent_id:
        return

    # Update purchase status
    purchase = (
        db.query(Purchase).filter(Purchase.stripe_payment_intent_id == payment_intent_id).first()
    )

    if purchase:
        purchase.status = "refunded"  # type: ignore[assignment]
        purchase.updated_at = datetime.utcnow()  # type: ignore[assignment]
        db.commit()

        # Recompute entitlements and invalidate cache
        recompute_and_store_entitlements(purchase.user_id, purchase.project_id, db)  # type: ignore[arg-type]
        invalidate_entitlements_cache(purchase.user_id, purchase.project_id)  # type: ignore[arg-type]


# Event type to processor mapping
EVENT_PROCESSORS: dict[str, Callable[[dict[str, Any], Session], None]] = {
    "checkout.session.completed": process_checkout_session_completed,
    "payment_intent.succeeded": process_payment_intent_succeeded,
    "payment_intent.payment_failed": process_payment_intent_failed,
    "customer.subscription.created": process_subscription_created,
    "customer.subscription.updated": process_subscription_updated,
    "customer.subscription.deleted": process_subscription_deleted,
    "invoice.payment_succeeded": process_invoice_payment_succeeded,
    "invoice.payment_failed": process_invoice_payment_failed,
    "charge.refunded": process_charge_refunded,
}
