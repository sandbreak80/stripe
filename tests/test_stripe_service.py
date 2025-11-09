"""Unit tests for Stripe service."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from billing_service.models import Project, StripeCustomer, User
from billing_service.stripe_service import (
    create_checkout_session,
    create_portal_session,
    get_or_create_stripe_customer,
)


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def test_user():
    """Create a test user object."""
    project = Project(id=1, name="test_project", active=True)
    user = User(id=1, project_id=1, external_user_id="user_123", email="test@example.com")
    user.project = project
    return user


@patch("billing_service.stripe_service.stripe.Customer.create")
def test_get_or_create_stripe_customer_new(mock_customer_create, mock_db_session, test_user):
    """Test creating a new Stripe customer."""
    # Mock database query returning None (customer doesn't exist)
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    
    # Mock Stripe customer creation
    mock_stripe_customer = MagicMock()
    mock_stripe_customer.id = "cus_test123"
    mock_customer_create.return_value = mock_stripe_customer
    
    # Call function
    get_or_create_stripe_customer(mock_db_session, test_user, email="test@example.com")
    
    # Verify Stripe customer was created
    mock_customer_create.assert_called_once()
    # Verify database record was added
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()


@patch("billing_service.stripe_service.stripe.Customer.create")
def test_get_or_create_stripe_customer_existing(mock_customer_create, mock_db_session, test_user):
    """Test retrieving an existing Stripe customer."""
    # Mock existing customer
    existing_customer = StripeCustomer(
        id=1,
        user_id=1,
        stripe_customer_id="cus_existing123",
    )
    mock_db_session.query.return_value.filter.return_value.first.return_value = existing_customer
    
    # Call function
    result = get_or_create_stripe_customer(mock_db_session, test_user)
    
    # Verify Stripe customer was NOT created
    mock_customer_create.assert_not_called()
    # Verify existing customer was returned
    assert result == existing_customer


@patch("billing_service.stripe_service.stripe.checkout.Session.create")
def test_create_checkout_session(mock_session_create, mock_db_session):
    """Test creating a checkout session."""
    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/test"
    mock_session_create.return_value = mock_session
    
    result = create_checkout_session(
        db=mock_db_session,
        stripe_customer_id="cus_test123",
        price_id="price_test123",
        mode="subscription",
        success_url="https://example.com/success",
        cancel_url="https://example.com/cancel",
        project_id=1,
    )
    
    assert result == "https://checkout.stripe.com/test"
    mock_session_create.assert_called_once()


@patch("billing_service.stripe_service.stripe.billing_portal.Session.create")
def test_create_portal_session(mock_portal_create):
    """Test creating a portal session."""
    mock_session = MagicMock()
    mock_session.url = "https://billing.stripe.com/test"
    mock_portal_create.return_value = mock_session
    
    result = create_portal_session(
        stripe_customer_id="cus_test123",
        return_url="https://example.com/return",
    )
    
    assert result == "https://billing.stripe.com/test"
    mock_portal_create.assert_called_once()
