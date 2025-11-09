"""Entitlement computation engine."""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from billing_service.models import (
    Entitlement,
    ManualGrant,
    Price,
    Purchase,
    Subscription,
)


def compute_entitlements(user_id: int, project_id: int, db: Session) -> list[dict[str, Any]]:
    """Compute effective entitlements from all sources."""
    now = datetime.utcnow()
    entitlements_map: dict[str, dict[str, Any]] = {}

    # 1. Process active subscriptions
    subscriptions = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.project_id == project_id,
            Subscription.status.in_(["trialing", "active"]),
        )
        .all()
    )

    for subscription in subscriptions:
        # Get feature code from price
        price = (
            db.query(Price).filter(Price.stripe_price_id == subscription.stripe_price_id).first()
        )
        if price and subscription.current_period_end and subscription.current_period_end > now:
            feature_code = str(price.feature_code)
            entitlements_map[feature_code] = {
                "feature_code": feature_code,
                "active": True,
                "source": "subscription",
                "source_id": subscription.id,
                "valid_from": subscription.current_period_start or subscription.created_at,
                "valid_to": subscription.current_period_end,
                "grant_created_at": subscription.created_at,  # Store for revoke comparison
            }

    # 2. Process successful purchases (one-time)
    purchases = (
        db.query(Purchase)
        .filter(
            Purchase.user_id == user_id,
            Purchase.project_id == project_id,
            Purchase.status == "succeeded",
        )
        .all()
    )

    for purchase in purchases:
        # Get feature code from price
        price = db.query(Price).filter(Price.stripe_price_id == purchase.stripe_price_id).first()
        if price:
            feature_code = str(price.feature_code)
            # For one-time purchases, check if we already have this from subscription
            # Purchases grant lifetime access (no valid_to) unless already covered
            if feature_code not in entitlements_map:
                entitlements_map[feature_code] = {
                    "feature_code": feature_code,
                    "active": True,
                    "source": "purchase",
                    "source_id": purchase.id,
                    "valid_from": purchase.created_at,
                    "valid_to": None,  # Lifetime access
                    "grant_created_at": purchase.created_at,  # Store for revoke comparison
                }

    # 3. Process manual grants
    manual_grants = (
        db.query(ManualGrant)
        .filter(
            ManualGrant.user_id == user_id,
            ManualGrant.project_id == project_id,
            ManualGrant.action == "grant",
        )
        .order_by(ManualGrant.created_at.desc())
        .all()
    )

    for grant in manual_grants:
        feature_code = str(grant.feature_code)
        # Manual grants can override or complement
        valid_from = grant.valid_from or grant.created_at
        valid_to = grant.valid_to

        # Check if still valid
        if valid_to and valid_to < now:
            continue

        if valid_from > now:
            continue

        # Manual grants take precedence
        entitlements_map[feature_code] = {
            "feature_code": feature_code,
            "active": True,
            "source": "manual",
            "source_id": grant.id,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "grant_created_at": grant.created_at,  # Store for revoke comparison
        }

    # 4. Check for revokes (manual revokes override everything)
    revokes = (
        db.query(ManualGrant)
        .filter(
            ManualGrant.user_id == user_id,
            ManualGrant.project_id == project_id,
            ManualGrant.action == "revoke",
        )
        .order_by(ManualGrant.created_at.desc())
        .all()
    )

    for revoke in revokes:
        feature_code = str(revoke.feature_code)
        # If revoke is newer than the grant, remove entitlement
        if feature_code in entitlements_map:
            # Compare revoke.created_at with grant.created_at (not valid_from)
            # For manual grants, we stored grant_created_at
            # For other grants, use valid_from as proxy (they're created when valid_from starts)
            grant_created_at = entitlements_map[feature_code].get("grant_created_at")
            if not grant_created_at:
                grant_created_at = entitlements_map[feature_code].get("valid_from")

            if grant_created_at and revoke.created_at > grant_created_at:
                del entitlements_map[feature_code]

    # Convert to list and filter by validity
    result = []
    for entitlement in entitlements_map.values():
        # Double-check validity
        if entitlement["valid_from"] > now:
            continue
        if entitlement["valid_to"] and entitlement["valid_to"] < now:
            continue
        result.append(entitlement)

    return result


def recompute_and_store_entitlements(user_id: int, project_id: int, db: Session) -> None:
    """Recompute entitlements and store in database."""
    # Delete existing computed entitlements
    db.query(Entitlement).filter(
        Entitlement.user_id == user_id, Entitlement.project_id == project_id
    ).delete()

    # Compute new entitlements
    computed = compute_entitlements(user_id, project_id, db)

    # Store in database
    for ent_data in computed:
        entitlement = Entitlement(
            user_id=user_id,
            project_id=project_id,
            feature_code=ent_data["feature_code"],
            source=ent_data["source"],
            source_id=ent_data["source_id"],
            active=ent_data["active"],
            valid_from=ent_data["valid_from"],
            valid_to=ent_data["valid_to"],
        )
        db.add(entitlement)

    db.commit()
