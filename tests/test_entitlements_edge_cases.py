"""Additional tests for entitlements edge cases."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from billing_service.models import ManualGrant, Price, Purchase, Subscription
from billing_service.entitlements import compute_entitlements


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock(spec=Session)


def test_compute_entitlements_expired_subscription(mock_db_session):
    """Test entitlements computation with expired subscription."""
    subscription = Subscription(
        id=1,
        user_id=1,
        project_id=1,
        stripe_subscription_id="sub_test",
        stripe_price_id="price_test",
        status="active",
        current_period_start=datetime.utcnow() - timedelta(days=60),
        current_period_end=datetime.utcnow() - timedelta(days=30),  # Expired
        created_at=datetime.utcnow() - timedelta(days=60),
    )
    
    price = Price(id=1, stripe_price_id="price_test", feature_code="premium")
    
    def query_side_effect(model):
        if model == Subscription:
            query_mock = MagicMock()
            query_mock.filter.return_value.all.return_value = [subscription]
            return query_mock
        elif model == Purchase:
            query_mock = MagicMock()
            query_mock.filter.return_value.all.return_value = []
            return query_mock
        elif model == ManualGrant:
            query_mock = MagicMock()
            query_mock.filter.return_value.order_by.return_value.all.return_value = []
            return query_mock
        elif model == Price:
            query_mock = MagicMock()
            query_mock.filter.return_value.first.return_value = price
            return query_mock
        return MagicMock()
    
    mock_db_session.query.side_effect = query_side_effect
    
    result = compute_entitlements(1, 1, mock_db_session)
    
    # Expired subscription should not grant entitlement
    assert len(result) == 0


def test_compute_entitlements_no_price(mock_db_session):
    """Test entitlements computation when price is not found."""
    subscription = Subscription(
        id=1,
        user_id=1,
        project_id=1,
        stripe_subscription_id="sub_test",
        stripe_price_id="price_unknown",
        status="active",
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30),
        created_at=datetime.utcnow(),
    )
    
    def query_side_effect(model):
        if model == Subscription:
            query_mock = MagicMock()
            query_mock.filter.return_value.all.return_value = [subscription]
            return query_mock
        elif model == Purchase:
            query_mock = MagicMock()
            query_mock.filter.return_value.all.return_value = []
            return query_mock
        elif model == ManualGrant:
            query_mock = MagicMock()
            query_mock.filter.return_value.order_by.return_value.all.return_value = []
            return query_mock
        elif model == Price:
            query_mock = MagicMock()
            query_mock.filter.return_value.first.return_value = None  # Price not found
            return query_mock
        return MagicMock()
    
    mock_db_session.query.side_effect = query_side_effect
    
    result = compute_entitlements(1, 1, mock_db_session)
    
    # No price means no entitlement
    assert len(result) == 0


def test_compute_entitlements_future_validity(mock_db_session):
    """Test entitlements computation with future validity window."""
    grant = ManualGrant(
        id=1,
        user_id=1,
        project_id=1,
        feature_code="premium",
        action="grant",
        granted_by="admin",
        created_at=datetime.utcnow(),
        valid_from=datetime.utcnow() + timedelta(days=1),  # Future
        valid_to=None,
    )
    
    def query_side_effect(model):
        if model == Subscription:
            query_mock = MagicMock()
            query_mock.filter.return_value.all.return_value = []
            return query_mock
        elif model == Purchase:
            query_mock = MagicMock()
            query_mock.filter.return_value.all.return_value = []
            return query_mock
        elif model == ManualGrant:
            query_mock = MagicMock()
            query_mock.filter.return_value.order_by.return_value.all.return_value = [grant]
            return query_mock
        return MagicMock()
    
    mock_db_session.query.side_effect = query_side_effect
    
    result = compute_entitlements(1, 1, mock_db_session)
    
    # Future validity should not grant entitlement yet
    assert len(result) == 0
