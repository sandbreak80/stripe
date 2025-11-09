"""Reconciliation system for Stripe data."""

from datetime import datetime, timedelta
from typing import Any

import stripe
from sqlalchemy.orm import Session

from billing_service.config import settings
from billing_service.entitlements import recompute_and_store_entitlements
from billing_service.models import Purchase, Subscription

# Initialize Stripe
stripe.api_key = settings.stripe_secret_key


def reconcile_subscriptions(db: Session, days_back: int = 7) -> dict[str, int]:
    """Reconcile subscriptions with Stripe."""
    cutoff_date = datetime.utcnow() - timedelta(days=days_back)

    # Get recent subscriptions from database
    local_subscriptions = (
        db.query(Subscription).filter(Subscription.updated_at >= cutoff_date).all()
    )

    drift_count = 0
    corrected_count = 0

    for local_sub in local_subscriptions:
        try:
            # Fetch from Stripe
            stripe_sub = stripe.Subscription.retrieve(str(local_sub.stripe_subscription_id))

            # Compare status
            if stripe_sub.status != local_sub.status:
                local_sub.status = stripe_sub.status  # type: ignore[assignment]
                drift_count += 1

            # Compare period end
            stripe_period_end = datetime.fromtimestamp(stripe_sub.current_period_end)
            # Use timedelta comparison to handle microsecond differences
            if local_sub.current_period_end:
                period_diff = abs(
                    (local_sub.current_period_end - stripe_period_end).total_seconds()
                )
                if period_diff > 1:  # More than 1 second difference
                    local_sub.current_period_end = stripe_period_end  # type: ignore[assignment]
                    drift_count += 1
            else:
                local_sub.current_period_end = stripe_period_end  # type: ignore[assignment]
                drift_count += 1

            if drift_count > 0:
                local_sub.updated_at = datetime.utcnow()  # type: ignore[assignment]
                db.commit()
                corrected_count += 1

                # Recompute entitlements
                user_id_val = int(local_sub.user_id)
                project_id_val = int(local_sub.project_id)
                recompute_and_store_entitlements(user_id_val, project_id_val, db)
        except Exception:
            # Subscription might have been deleted in Stripe or other error
            continue

    return {
        "subscriptions_checked": len(local_subscriptions),
        "drift_detected": drift_count,
        "corrected": corrected_count,
    }


def reconcile_purchases(db: Session, days_back: int = 7) -> dict[str, int]:
    """Reconcile purchases with Stripe."""
    cutoff_date = datetime.utcnow() - timedelta(days=days_back)

    # Get recent purchases from database
    local_purchases = db.query(Purchase).filter(Purchase.updated_at >= cutoff_date).all()

    drift_count = 0
    corrected_count = 0

    for local_purchase in local_purchases:
        try:
            # Fetch payment intent from Stripe
            payment_intent = stripe.PaymentIntent.retrieve(
                str(local_purchase.stripe_payment_intent_id)
            )

            # Compare status
            stripe_status = "succeeded" if payment_intent.status == "succeeded" else "failed"
            if stripe_status != local_purchase.status:
                local_purchase.status = stripe_status  # type: ignore[assignment]
                local_purchase.updated_at = datetime.utcnow()  # type: ignore[assignment]
                drift_count += 1
                corrected_count += 1
                db.commit()

                # Recompute entitlements
                user_id_val = int(local_purchase.user_id)
                project_id_val = int(local_purchase.project_id)
                recompute_and_store_entitlements(user_id_val, project_id_val, db)
        except Exception:
            # Payment intent might not exist or other error
            continue

    return {
        "purchases_checked": len(local_purchases),
        "drift_detected": drift_count,
        "corrected": corrected_count,
    }


def reconcile_all(db: Session, days_back: int = 7) -> dict[str, Any]:
    """Run full reconciliation."""
    sub_result = reconcile_subscriptions(db, days_back)
    purchase_result = reconcile_purchases(db, days_back)

    return {
        "reconciliation_date": datetime.utcnow().isoformat(),
        "days_back": days_back,
        "subscriptions": sub_result,
        "purchases": purchase_result,
    }
