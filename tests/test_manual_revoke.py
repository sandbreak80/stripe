"""Test manual revoke functionality."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from billing_service.models import ManualGrant
from billing_service.entitlements import compute_entitlements


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock(spec=Session)


def test_compute_entitlements_manual_revoke(mock_db_session):
    """Test entitlements computation with manual revoke."""
    grant = ManualGrant(
        id=1,
        user_id=1,
        project_id=1,
        feature_code="premium",
        action="grant",
        granted_by="admin",
        created_at=datetime.utcnow() - timedelta(days=10),
        valid_from=datetime.utcnow() - timedelta(days=10),
        valid_to=None,
    )
    
    revoke = ManualGrant(
        id=2,
        user_id=1,
        project_id=1,
        feature_code="premium",
        action="revoke",
        granted_by="admin",
        created_at=datetime.utcnow() - timedelta(days=3),  # Newer than grant.created_at
    )
    
    # Track ManualGrant queries - grants first, then revokes
    manual_grant_call_count = 0
    
    def query_side_effect(model):
        nonlocal manual_grant_call_count
        query_mock = MagicMock()
        filter_mock = MagicMock()
        
        if model == ManualGrant:
            manual_grant_call_count += 1
            order_by_mock = MagicMock()
            if manual_grant_call_count == 1:
                # First call - grants query
                order_by_mock.all.return_value = [grant]
            else:
                # Second call - revokes query
                order_by_mock.all.return_value = [revoke]
            filter_mock.order_by.return_value = order_by_mock
            query_mock.filter.return_value = filter_mock
        else:
            filter_mock.all.return_value = []
            filter_mock.first.return_value = None
            query_mock.filter.return_value = filter_mock
        
        return query_mock
    
    mock_db_session.query.side_effect = query_side_effect
    
    result = compute_entitlements(1, 1, mock_db_session)
    
    # Revoke should remove the entitlement (revoke.created_at > grant.created_at)
    assert len(result) == 0
