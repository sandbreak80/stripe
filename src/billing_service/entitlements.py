"""Entitlements computation logic."""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from billing_service.models import (
    Entitlement,
    EntitlementSource,
    ManualGrant,
    Price,
    Product,
    Purchase,
    PurchaseStatus,
    Subscription,
    SubscriptionStatus,
)

logger = logging.getLogger(__name__)


def compute_entitlements_for_user(
    db: Session, user_id: str, project_id: UUID
) -> list[Entitlement]:
    """
    Compute entitlements for a user in a project.

    This function aggregates entitlements from:
    - Active subscriptions (with valid periods)
    - Succeeded purchases (not refunded)
    - Active manual grants (not revoked, within validity period)

    Args:
        db: Database session
        user_id: User identifier
        project_id: Project UUID

    Returns:
        List of computed Entitlement objects
    """
    now = datetime.utcnow()
    entitlements: list[Entitlement] = []

    # 1. Process active subscriptions
    active_subscriptions = (
        db.query(Subscription)
        .join(Price, Subscription.price_id == Price.id)
        .join(Product, Price.product_id == Product.id)
        .filter(
            Subscription.user_id == user_id,
            Subscription.project_id == project_id,
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]),
        )
        .all()
    )

    for subscription in active_subscriptions:
        # Get product through price relationship
        price = subscription.price  # type: ignore
        if not price:
            logger.warning(f"Price not found for subscription {subscription.stripe_subscription_id}")
            continue

        product = price.product  # type: ignore
        if not product or not product.feature_codes:
            logger.warning(f"Product not found or has no features for subscription {subscription.stripe_subscription_id}")
            continue

        # Determine validity period
        valid_from = subscription.current_period_start
        valid_to = subscription.current_period_end

        # If subscription is canceled but cancel_at_period_end is True, still valid until period end
        if subscription.status == SubscriptionStatus.CANCELED and subscription.cancel_at_period_end:
            # Already handled by valid_to = current_period_end
            pass
        elif subscription.status == SubscriptionStatus.CANCELED:
            # Immediately canceled, no entitlements
            continue

        # Create entitlements for each feature
        for feature_code in product.feature_codes:
            entitlement = Entitlement(
                user_id=user_id,
                project_id=project_id,
                feature_code=feature_code,
                is_active=True,
                valid_from=valid_from,
                valid_to=valid_to,
                source=EntitlementSource.SUBSCRIPTION,
                source_id=subscription.id,
                computed_at=now,
            )
            entitlements.append(entitlement)

    # 2. Process succeeded purchases (not refunded)
    succeeded_purchases = (
        db.query(Purchase)
        .join(Price, Purchase.price_id == Price.id)
        .join(Product, Price.product_id == Product.id)
        .filter(
            Purchase.user_id == user_id,
            Purchase.project_id == project_id,
            Purchase.status == PurchaseStatus.SUCCEEDED,
        )
        .all()
    )

    for purchase in succeeded_purchases:
        # Get product through price relationship
        price = purchase.price  # type: ignore
        if not price:
            logger.warning(f"Price not found for purchase {purchase.stripe_charge_id}")
            continue

        product = price.product  # type: ignore
        if not product or not product.feature_codes:
            logger.warning(f"Product not found or has no features for purchase {purchase.stripe_charge_id}")
            continue

        # Determine validity period
        valid_from = purchase.valid_from
        valid_to = purchase.valid_to  # Can be None for lifetime purchases

        # Check if purchase is still valid
        if valid_to and valid_to < now:
            continue  # Expired purchase

        # Create entitlements for each feature
        for feature_code in product.feature_codes:
            entitlement = Entitlement(
                user_id=user_id,
                project_id=project_id,
                feature_code=feature_code,
                is_active=True,
                valid_from=valid_from,
                valid_to=valid_to,
                source=EntitlementSource.PURCHASE,
                source_id=purchase.id,
                computed_at=now,
            )
            entitlements.append(entitlement)

    # 3. Process active manual grants
    active_grants = (
        db.query(ManualGrant)
        .filter(
            ManualGrant.user_id == user_id,
            ManualGrant.project_id == project_id,
            ManualGrant.revoked_at.is_(None),  # Not revoked
            ManualGrant.valid_from <= now,  # Already started
        )
        .all()
    )

    for grant in active_grants:
        # Check if grant is still valid
        if grant.valid_to and grant.valid_to < now:
            continue  # Expired grant

        entitlement = Entitlement(
            user_id=user_id,
            project_id=project_id,
            feature_code=grant.feature_code,
            is_active=True,
            valid_from=grant.valid_from,
            valid_to=grant.valid_to,
            source=EntitlementSource.MANUAL,
            source_id=grant.id,
            computed_at=now,
        )
        entitlements.append(entitlement)

    return entitlements


def recompute_and_store_entitlements(db: Session, user_id: str, project_id: UUID) -> None:
    """
    Recompute entitlements for a user and store them in the database.

    This function:
    1. Computes current entitlements
    2. Deletes old entitlements for this user/project
    3. Stores new entitlements

    Args:
        db: Database session
        user_id: User identifier
        project_id: Project UUID
    """
    # Compute new entitlements
    new_entitlements = compute_entitlements_for_user(db, user_id, project_id)

    # Delete old entitlements for this user/project
    db.query(Entitlement).filter(
        Entitlement.user_id == user_id,
        Entitlement.project_id == project_id,
    ).delete()

    # Store new entitlements
    for entitlement in new_entitlements:
        db.add(entitlement)

    db.commit()
    logger.info(
        f"Recomputed {len(new_entitlements)} entitlements for user {user_id} in project {project_id}"
    )
