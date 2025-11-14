"""Reconciliation system for syncing Stripe data with local database."""

import logging
from datetime import datetime

import stripe
from sqlalchemy.orm import Session

from billing_service.config import settings
from billing_service.database import SessionLocal
from billing_service.entitlements import recompute_and_store_entitlements
from billing_service.models import (
    Project,
    Purchase,
    PurchaseStatus,
    Subscription,
    SubscriptionStatus,
)

logger = logging.getLogger(__name__)


class ReconciliationResult:
    """Result of reconciliation operation."""

    def __init__(self):
        self.subscriptions_synced = 0
        self.subscriptions_updated = 0
        self.subscriptions_missing_in_stripe = 0
        self.purchases_synced = 0
        self.purchases_updated = 0
        self.purchases_missing_in_stripe = 0
        self.errors: list[str] = []


def reconcile_subscription(
    db: Session, subscription: Subscription, stripe_subscription: stripe.Subscription
) -> bool:
    """
    Reconcile a single subscription with Stripe data.

    Returns True if subscription was updated, False otherwise.
    """
    updated = False

    # Map Stripe status
    status_map = {
        "active": SubscriptionStatus.ACTIVE,
        "trialing": SubscriptionStatus.TRIALING,
        "past_due": SubscriptionStatus.PAST_DUE,
        "canceled": SubscriptionStatus.CANCELED,
        "unpaid": SubscriptionStatus.UNPAID,
    }
    stripe_status = getattr(stripe_subscription, "status", "active")
    new_status = status_map.get(stripe_status, SubscriptionStatus.ACTIVE)

    # Update status if changed
    if subscription.status != new_status:
        subscription.status = new_status  # type: ignore[assignment]
        updated = True

    # Update period dates
    new_period_start = datetime.fromtimestamp(getattr(stripe_subscription, "current_period_start", 0))
    new_period_end = datetime.fromtimestamp(getattr(stripe_subscription, "current_period_end", 0))

    if subscription.current_period_start != new_period_start:
        subscription.current_period_start = new_period_start  # type: ignore[assignment]
        updated = True

    if subscription.current_period_end != new_period_end:
        subscription.current_period_end = new_period_end  # type: ignore[assignment]
        updated = True

    # Update cancellation flags
    new_cancel_at_period_end = getattr(stripe_subscription, "cancel_at_period_end", False) or False
    if subscription.cancel_at_period_end != new_cancel_at_period_end:
        subscription.cancel_at_period_end = new_cancel_at_period_end  # type: ignore[assignment]
        updated = True

    canceled_at_ts = getattr(stripe_subscription, "canceled_at", None)
    new_canceled_at = datetime.fromtimestamp(canceled_at_ts) if canceled_at_ts else None
    if subscription.canceled_at != new_canceled_at:
        subscription.canceled_at = new_canceled_at  # type: ignore[assignment]
        updated = True

    return updated


def reconcile_subscriptions_for_project(db: Session, project: Project) -> tuple[int, int, int]:
    """
    Reconcile all subscriptions for a project.

    Returns (synced_count, updated_count, missing_count).
    """
    synced = 0
    updated = 0
    missing = 0

    subscriptions = db.query(Subscription).filter(Subscription.project_id == project.id).all()

    stripe.api_key = settings.stripe_secret_key

    for subscription in subscriptions:
        try:
            # Retrieve from Stripe
            stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)

            # Reconcile
            was_updated = reconcile_subscription(db, subscription, stripe_subscription)
            if was_updated:
                db.commit()
                updated += 1
                # Recompute entitlements
                recompute_and_store_entitlements(db, subscription.user_id, subscription.project_id)
            synced += 1

        except stripe.error.InvalidRequestError:
            # Subscription doesn't exist in Stripe
            logger.warning(
                f"Subscription {subscription.stripe_subscription_id} not found in Stripe",
                extra={"subscription_id": subscription.stripe_subscription_id},
            )
            missing += 1
        except Exception as e:
            logger.error(
                f"Error reconciling subscription {subscription.stripe_subscription_id}: {e}",
                extra={"subscription_id": subscription.stripe_subscription_id},
                exc_info=True,
            )
            # Continue with next subscription instead of failing entire reconciliation
            # Error is logged for investigation

    return (synced, updated, missing)


def reconcile_purchase(
    db: Session, purchase: Purchase, stripe_charge: stripe.Charge
) -> bool:
    """
    Reconcile a single purchase with Stripe charge data.

    Returns True if purchase was updated, False otherwise.
    """
    updated = False

    # Check refund status
    is_refunded = getattr(stripe_charge, "refunded", False)
    if is_refunded and purchase.status != PurchaseStatus.REFUNDED:
        purchase.status = PurchaseStatus.REFUNDED  # type: ignore[assignment]
        purchase.refunded_at = datetime.utcnow()  # type: ignore[assignment]
        updated = True
    elif not is_refunded and purchase.status == PurchaseStatus.REFUNDED:
        # Charge was refunded but we marked it as refunded - this is correct
        # No action needed, state is already correct
        logger.debug(
            f"Purchase {purchase.stripe_charge_id} already marked as refunded, no update needed"
        )

    return updated


def reconcile_purchases_for_project(db: Session, project: Project) -> tuple[int, int, int]:
    """
    Reconcile all purchases for a project.

    Returns (synced_count, updated_count, missing_count).
    """
    synced = 0
    updated = 0
    missing = 0

    purchases = db.query(Purchase).filter(Purchase.project_id == project.id).all()

    stripe.api_key = settings.stripe_secret_key

    for purchase in purchases:
        try:
            # Retrieve from Stripe
            stripe_charge = stripe.Charge.retrieve(purchase.stripe_charge_id)

            # Reconcile
            was_updated = reconcile_purchase(db, purchase, stripe_charge)
            if was_updated:
                db.commit()
                updated += 1
                # Recompute entitlements
                recompute_and_store_entitlements(db, purchase.user_id, purchase.project_id)
            synced += 1

        except stripe.error.InvalidRequestError:
            # Charge doesn't exist in Stripe
            logger.warning(
                f"Charge {purchase.stripe_charge_id} not found in Stripe",
                extra={"charge_id": purchase.stripe_charge_id},
            )
            missing += 1
        except Exception as e:
            logger.error(
                f"Error reconciling purchase {purchase.stripe_charge_id}: {e}",
                extra={"charge_id": purchase.stripe_charge_id},
                exc_info=True,
            )
            # Continue with next purchase instead of failing entire reconciliation
            # Error is logged for investigation

    return (synced, updated, missing)


def reconcile_all() -> ReconciliationResult:
    """
    Reconcile all projects with Stripe.

    This function should be called daily via a scheduled job.
    """
    result = ReconciliationResult()
    db = SessionLocal()

    try:
        projects = db.query(Project).filter(Project.is_active == True).all()  # noqa: E712

        for project in projects:
            logger.info(f"Reconciling project {project.project_id}")

            # Reconcile subscriptions
            sub_synced, sub_updated, sub_missing = reconcile_subscriptions_for_project(db, project)
            result.subscriptions_synced += sub_synced
            result.subscriptions_updated += sub_updated
            result.subscriptions_missing_in_stripe += sub_missing

            # Reconcile purchases
            pur_synced, pur_updated, pur_missing = reconcile_purchases_for_project(db, project)
            result.purchases_synced += pur_synced
            result.purchases_updated += pur_updated
            result.purchases_missing_in_stripe += pur_missing

        logger.info(
            f"Reconciliation complete: "
            f"{result.subscriptions_synced} subscriptions synced, "
            f"{result.subscriptions_updated} updated, "
            f"{result.subscriptions_missing_in_stripe} missing; "
            f"{result.purchases_synced} purchases synced, "
            f"{result.purchases_updated} updated, "
            f"{result.purchases_missing_in_stripe} missing"
        )

    except Exception as e:
        logger.error(f"Error during reconciliation: {e}", exc_info=True)
        result.errors.append(str(e))
    finally:
        db.close()

    return result
