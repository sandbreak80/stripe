"""Fixtures for integration tests with real Stripe API."""

import os
import pytest
import stripe
from typing import Generator

from billing_service.config import settings


# Check if we should use real Stripe APIs
USE_REAL_STRIPE = os.getenv("USE_REAL_STRIPE", "false").lower() in ("true", "1", "yes")
STRIPE_SECRET_KEY = settings.stripe_secret_key if USE_REAL_STRIPE and settings.stripe_secret_key else None


@pytest.fixture(scope="session")
def stripe_api_configured():
    """Check if Stripe API is configured for integration tests."""
    if not USE_REAL_STRIPE:
        pytest.skip("USE_REAL_STRIPE not set - skipping real Stripe API tests")
    
    if not STRIPE_SECRET_KEY or not STRIPE_SECRET_KEY.startswith("sk_test_"):
        pytest.skip("Stripe test secret key not configured - skipping real Stripe API tests")
    
    stripe.api_key = STRIPE_SECRET_KEY
    return True


@pytest.fixture
def stripe_product(stripe_api_configured) -> Generator[stripe.Product, None, None]:
    """Create a real Stripe product for testing."""
    product = stripe.Product.create(
        name="Test Product",
        description="Test product for integration tests",
        metadata={"test": "true"},
    )
    
    yield product
    
    # Cleanup: archive the product (can't delete products with prices)
    try:
        stripe.Product.modify(product.id, active=False)
    except Exception:
        pass


@pytest.fixture
def stripe_price(stripe_product) -> Generator[stripe.Price, None, None]:
    """Create a real Stripe price for testing."""
    price = stripe.Price.create(
        currency="usd",
        unit_amount=999,  # $9.99
        recurring={"interval": "month"},
        product=stripe_product.id,
        metadata={"test": "true"},
    )
    
    yield price
    
    # Cleanup: archive the price
    try:
        stripe.Price.modify(price.id, active=False)
    except Exception:
        pass


@pytest.fixture
def stripe_customer(stripe_api_configured) -> Generator[stripe.Customer, None, None]:
    """Create a real Stripe customer for testing."""
    customer = stripe.Customer.create(
        email="test@example.com",
        metadata={"test": "true"},
    )
    
    yield customer
    
    # Cleanup: delete the customer
    try:
        stripe.Customer.delete(customer.id)
    except Exception:
        pass


@pytest.fixture
def stripe_test_card():
    """Return a Stripe test card token."""
    # These are Stripe test card numbers that always succeed
    return {
        "number": "4242424242424242",
        "exp_month": 12,
        "exp_year": 2025,
        "cvc": "123",
    }


@pytest.fixture
def stripe_payment_method(stripe_customer, stripe_api_configured) -> Generator[stripe.PaymentMethod, None, None]:
    """Create a real Stripe payment method for testing.
    
    NOTE: This fixture requires "Test mode card data" to be enabled in your Stripe Dashboard
    (Settings > Integrations > Test mode card data). 
    
    Stripe discourages passing full card numbers even in test mode. If you haven't enabled
    this setting, you'll need to either:
    1. Enable it in Stripe Dashboard (recommended for integration tests)
    2. Skip tests that use this fixture
    3. Use Stripe Elements or other secure collection methods in your application
    
    See: https://support.stripe.com/questions/enabling-access-to-raw-card-data-apis
    """
    try:
        # In Stripe test mode with "Test mode card data" enabled, you can use test card numbers
        # These are Stripe's official test card numbers that work in test mode
        payment_method = stripe.PaymentMethod.create(
            type="card",
            card={
                "number": "4242424242424242",  # Visa test card
                "exp_month": 12,
                "exp_year": 2025,
                "cvc": "123",
            },
        )
        
        # Attach to customer
        stripe.PaymentMethod.attach(
            payment_method.id,
            customer=stripe_customer.id,
        )
        
        yield payment_method
        
    except stripe.error.CardError as e:
        if "raw card data" in str(e).lower() or "unsafe" in str(e).lower():
            pytest.skip(
                "Test mode card data not enabled. Enable it in Stripe Dashboard: "
                "Settings > Integrations > Test mode card data. "
                "See: https://support.stripe.com/questions/enabling-access-to-raw-card-data-apis"
            )
        raise
    finally:
        # Cleanup: detach and delete payment method
        try:
            if 'payment_method' in locals():
                stripe.PaymentMethod.detach(payment_method.id)
        except Exception:
            pass


@pytest.fixture
def stripe_checkout_session(stripe_price, stripe_api_configured) -> Generator[stripe.checkout.Session, None, None]:
    """Create a real Stripe checkout session for testing."""
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{"price": stripe_price.id, "quantity": 1}],
        mode="subscription",
        success_url="https://example.com/success",
        cancel_url="https://example.com/cancel",
        metadata={"test": "true"},
    )
    
    yield session
    
    # Checkout sessions can't be deleted, but they expire naturally


def cleanup_stripe_test_data():
    """Cleanup function to remove all test data from Stripe."""
    if not STRIPE_SECRET_KEY:
        return
    
    stripe.api_key = STRIPE_SECRET_KEY
    
    # List and archive/delete test products
    try:
        products = stripe.Product.list(limit=100, active=True)
        for product in products.data:
            if product.metadata.get("test") == "true":
                try:
                    # Archive associated prices first
                    prices = stripe.Price.list(product=product.id, limit=100)
                    for price in prices.data:
                        stripe.Price.modify(price.id, active=False)
                    stripe.Product.modify(product.id, active=False)
                except Exception:
                    pass
    except Exception:
        pass
    
    # List and delete test customers
    try:
        customers = stripe.Customer.list(limit=100)
        for customer in customers.data:
            if customer.metadata.get("test") == "true":
                try:
                    stripe.Customer.delete(customer.id)
                except Exception:
                    pass
    except Exception:
        pass

