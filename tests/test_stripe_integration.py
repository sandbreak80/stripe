"""Integration tests using real Stripe API."""

import pytest
from datetime import datetime
import hashlib

from billing_service.main import app
from billing_service.database import get_db
from billing_service.auth import verify_project_api_key
from billing_service.models import Price, Product, PriceInterval


@pytest.mark.integration_stripe
@pytest.mark.asyncio
async def test_create_checkout_session_real_stripe(
    client, db_session, test_project, stripe_product, stripe_price
):
    """Test creating a checkout session with real Stripe API."""
    # Create a price in our database that references the Stripe price
    product = Product(
        product_id="test-product-real",
        project_id=test_project.id,
        name="Test Product",
        description="Test product",
        feature_codes=["feature1"],
        is_archived=False,
    )
    db_session.add(product)
    db_session.flush()
    
    price = Price(
        stripe_price_id=stripe_price.id,
        product_id=product.id,
        amount=stripe_price.unit_amount or 999,
        currency="usd",
        interval=PriceInterval.MONTH,
        is_archived=False,
    )
    db_session.add(price)
    db_session.commit()
    db_session.refresh(price)
    
    # Set up API key
    api_key = "test_checkout_key_real"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    test_project.api_key_hash = api_key_hash
    db_session.commit()
    db_session.refresh(test_project)
    
    # Override dependencies
    async def override_get_db():
        from sqlalchemy.orm import sessionmaker
        TestingSessionLocal = sessionmaker(bind=db_session.bind)
        test_session = TestingSessionLocal()
        try:
            yield test_session
        finally:
            test_session.close()
    
    async def override_verify():
        return test_project
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_project_api_key] = override_verify
    
    try:
        # Create checkout session with real Stripe API
        response = await client.post(
            "/api/v1/checkout/create",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "user_id": "user_real_test",
                "project_id": "test-project",
                "price_id": str(price.id),
                "mode": "subscription",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "checkout_url" in data
        assert data["checkout_url"].startswith("https://checkout.stripe.com")
        assert "session_id" in data
        assert data["session_id"].startswith("cs_")
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration_stripe
def test_stripe_price_creation(stripe_product):
    """Test that we can create a Stripe price."""
    import stripe
    from billing_service.config import settings
    
    stripe.api_key = settings.stripe_secret_key
    
    price = stripe.Price.create(
        currency="usd",
        unit_amount=1999,  # $19.99
        recurring={"interval": "month"},
        product=stripe_product.id,
        metadata={"test": "true"},
    )
    
    assert price.id.startswith("price_")
    assert price.currency == "usd"
    assert price.unit_amount == 1999
    assert price.recurring is not None
    assert price.recurring.interval == "month"
    
    # Cleanup
    stripe.Price.modify(price.id, active=False)


@pytest.mark.integration_stripe
def test_stripe_customer_creation(stripe_customer):
    """Test that we can create a Stripe customer."""
    assert stripe_customer.id.startswith("cus_")
    assert stripe_customer.email == "test@example.com"


@pytest.mark.integration_stripe
def test_stripe_checkout_session_creation(stripe_checkout_session):
    """Test that we can create a Stripe checkout session."""
    assert stripe_checkout_session.id.startswith("cs_")
    assert stripe_checkout_session.url is not None
    assert stripe_checkout_session.url.startswith("https://checkout.stripe.com")


@pytest.mark.integration_stripe
@pytest.mark.asyncio
async def test_reconciliation_with_real_stripe(
    client, db_session, test_project, stripe_product, stripe_price, stripe_customer, stripe_payment_method
):
    """Test reconciliation with real Stripe subscriptions."""
    import stripe
    from billing_service.reconciliation import reconcile_subscriptions_for_project
    from billing_service.models import Subscription, SubscriptionStatus
    
    # Payment method is already attached in the fixture
    # Just ensure it's set as default payment method
    try:
        stripe.Customer.modify(
            stripe_customer.id,
            invoice_settings={"default_payment_method": stripe_payment_method.id},
        )
    except Exception:
        # If already set or fails, continue anyway
        pass
    
    # Create a subscription in Stripe
    stripe_subscription = stripe.Subscription.create(
        customer=stripe_customer.id,
        items=[{"price": stripe_price.id}],
        metadata={"test": "true", "project_id": str(test_project.project_id)},
    )
    
    # Create corresponding subscription in our database
    product = Product(
        product_id="test-product-recon",
        project_id=test_project.id,
        name="Test Product",
        description="Test product",
        feature_codes=["feature1"],
        is_archived=False,
    )
    db_session.add(product)
    db_session.flush()
    
    price = Price(
        stripe_price_id=stripe_price.id,
        product_id=product.id,
        amount=999,
        currency="usd",
        interval=PriceInterval.MONTH,
        is_archived=False,
    )
    db_session.add(price)
    db_session.flush()
    
    subscription = Subscription(
        stripe_subscription_id=stripe_subscription.id,
        user_id="user_recon_test",
        project_id=test_project.id,
        price_id=price.id,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start),
        current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end),
        cancel_at_period_end=False,
        canceled_at=None,
    )
    db_session.add(subscription)
    db_session.commit()
    
    # Run reconciliation
    synced, updated, missing = reconcile_subscriptions_for_project(db_session, test_project)
    
    # Should have synced 1 subscription
    assert synced >= 1
    
    # Cleanup: cancel subscription in Stripe
    stripe.Subscription.cancel(stripe_subscription.id)

