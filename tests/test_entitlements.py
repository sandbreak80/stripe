"""Tests for entitlements computation logic."""

from datetime import datetime, timedelta
import uuid

import pytest

from billing_service.entitlements import compute_entitlements_for_user, recompute_and_store_entitlements
from billing_service.models import (
    Entitlement,
    EntitlementSource,
    ManualGrant,
    Purchase,
    PurchaseStatus,
    Subscription,
    SubscriptionStatus,
)


def test_compute_entitlements_from_subscription(db_session, test_project, test_product, test_price):
    """Test computing entitlements from an active subscription."""
    # Use unique IDs to ensure test isolation
    unique_user_id = f"user_{uuid.uuid4().hex[:24]}"
    unique_sub_id = f"sub_{uuid.uuid4().hex[:24]}"

    # Clean up any existing entitlements for this user/project combination
    db_session.query(Entitlement).filter(
        Entitlement.user_id == unique_user_id,
        Entitlement.project_id == test_project.id,
    ).delete(synchronize_session=False)
    db_session.commit()

    # Create subscription
    subscription = Subscription(
        stripe_subscription_id=unique_sub_id,
        user_id=unique_user_id,
        project_id=test_project.id,
        price_id=test_price.id,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
        cancel_at_period_end=False,
    )
    db_session.add(subscription)
    db_session.commit()

    # Compute entitlements
    entitlements = compute_entitlements_for_user(db_session, unique_user_id, test_project.id)

    # Verify entitlements
    assert len(entitlements) == 2  # Two features
    assert all(e.user_id == unique_user_id for e in entitlements)
    assert all(e.project_id == test_project.id for e in entitlements)
    assert all(e.source == EntitlementSource.SUBSCRIPTION for e in entitlements)
    assert all(e.is_active is True for e in entitlements)
    assert {e.feature_code for e in entitlements} == {"feature1", "feature2"}


def test_compute_entitlements_from_purchase(db_session, test_project, test_product, test_price):
    """Test computing entitlements from a succeeded purchase."""
    user_id = "user_456"

    # Create purchase
    purchase = Purchase(
        stripe_charge_id="ch_test123",
        user_id=user_id,
        project_id=test_project.id,
        price_id=test_price.id,
        amount=999,
        currency="usd",
        status=PurchaseStatus.SUCCEEDED,
        valid_from=datetime.utcnow(),
        valid_to=None,  # Lifetime
    )
    db_session.add(purchase)
    db_session.commit()

    # Compute entitlements
    entitlements = compute_entitlements_for_user(db_session, user_id, test_project.id)

    # Verify entitlements
    assert len(entitlements) == 2
    assert all(e.source == EntitlementSource.PURCHASE for e in entitlements)
    assert all(e.valid_to is None for e in entitlements)  # Lifetime


def test_compute_entitlements_from_manual_grant(db_session, test_project):
    """Test computing entitlements from a manual grant."""
    user_id = "user_789"

    # Create manual grant
    grant = ManualGrant(
        user_id=user_id,
        project_id=test_project.id,
        feature_code="feature1",
        valid_from=datetime.utcnow(),
        valid_to=datetime.utcnow() + timedelta(days=7),
        reason="Test grant",
        granted_by="admin@test.com",
    )
    db_session.add(grant)
    db_session.commit()

    # Compute entitlements
    entitlements = compute_entitlements_for_user(db_session, user_id, test_project.id)

    # Verify entitlements
    assert len(entitlements) == 1
    assert entitlements[0].source == EntitlementSource.MANUAL
    assert entitlements[0].feature_code == "feature1"


def test_compute_entitlements_combines_sources(db_session, test_project, test_product, test_price):
    """Test that entitlements from multiple sources are combined."""
    user_id = "user_combined"

    # Create subscription
    subscription = Subscription(
        stripe_subscription_id="sub_combined",
        user_id=user_id,
        project_id=test_project.id,
        price_id=test_price.id,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
        cancel_at_period_end=False,
    )
    db_session.add(subscription)

    # Create manual grant for different feature
    grant = ManualGrant(
        user_id=user_id,
        project_id=test_project.id,
        feature_code="feature3",
        valid_from=datetime.utcnow(),
        valid_to=datetime.utcnow() + timedelta(days=7),
        reason="Test grant",
        granted_by="admin@test.com",
    )
    db_session.add(grant)
    db_session.commit()

    # Compute entitlements
    entitlements = compute_entitlements_for_user(db_session, user_id, test_project.id)

    # Should have 3 entitlements: 2 from subscription, 1 from grant
    assert len(entitlements) == 3
    assert len([e for e in entitlements if e.source == EntitlementSource.SUBSCRIPTION]) == 2
    assert len([e for e in entitlements if e.source == EntitlementSource.MANUAL]) == 1


def test_compute_entitlements_excludes_canceled_subscription(db_session, test_project, test_product, test_price):
    """Test that canceled subscriptions don't grant entitlements."""
    user_id = "user_canceled"

    # Create canceled subscription
    subscription = Subscription(
        stripe_subscription_id="sub_canceled",
        user_id=user_id,
        project_id=test_project.id,
        price_id=test_price.id,
        status=SubscriptionStatus.CANCELED,
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
        cancel_at_period_end=False,
    )
    db_session.add(subscription)
    db_session.commit()

    # Compute entitlements
    entitlements = compute_entitlements_for_user(db_session, user_id, test_project.id)

    # Should have no entitlements
    assert len(entitlements) == 0


def test_compute_entitlements_excludes_refunded_purchase(db_session, test_project, test_product, test_price):
    """Test that refunded purchases don't grant entitlements."""
    user_id = "user_refunded"

    # Create refunded purchase
    purchase = Purchase(
        stripe_charge_id="ch_refunded",
        user_id=user_id,
        project_id=test_project.id,
        price_id=test_price.id,
        amount=999,
        currency="usd",
        status=PurchaseStatus.REFUNDED,
        valid_from=datetime.utcnow(),
        valid_to=None,
    )
    db_session.add(purchase)
    db_session.commit()

    # Compute entitlements
    entitlements = compute_entitlements_for_user(db_session, user_id, test_project.id)

    # Should have no entitlements
    assert len(entitlements) == 0


def test_recompute_and_store_entitlements(db_session, test_project, test_product, test_price):
    """Test recomputing and storing entitlements."""
    user_id = "user_recompute"

    # Create subscription
    subscription = Subscription(
        stripe_subscription_id="sub_recompute",
        user_id=user_id,
        project_id=test_project.id,
        price_id=test_price.id,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
        cancel_at_period_end=False,
    )
    db_session.add(subscription)
    db_session.commit()

    # Recompute and store
    recompute_and_store_entitlements(db_session, user_id, test_project.id)

    # Verify stored entitlements
    stored = db_session.query(Entitlement).filter(
        Entitlement.user_id == user_id,
        Entitlement.project_id == test_project.id,
    ).all()

    assert len(stored) == 2
    assert all(e.is_active is True for e in stored)


def test_recompute_entitlements_updates_existing(db_session, test_project, test_product, test_price):
    """Test that recomputing updates existing entitlements."""
    user_id = "user_update"

    # Create initial subscription
    subscription1 = Subscription(
        stripe_subscription_id="sub_update1",
        user_id=user_id,
        project_id=test_project.id,
        price_id=test_price.id,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
        cancel_at_period_end=False,
    )
    db_session.add(subscription1)
    db_session.commit()

    # First recompute
    recompute_and_store_entitlements(db_session, user_id, test_project.id)
    first_count = db_session.query(Entitlement).filter(
        Entitlement.user_id == user_id,
        Entitlement.project_id == test_project.id,
    ).count()
    assert first_count == 2

    # Cancel subscription
    subscription1.status = SubscriptionStatus.CANCELED
    db_session.commit()

    # Recompute again
    recompute_and_store_entitlements(db_session, user_id, test_project.id)
    second_count = db_session.query(Entitlement).filter(
        Entitlement.user_id == user_id,
        Entitlement.project_id == test_project.id,
    ).count()
    assert second_count == 0  # No entitlements after cancellation
