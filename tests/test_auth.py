"""Unit tests for authentication."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from billing_service.auth import get_app_from_api_key
from billing_service.models import App, Project


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def test_app():
    """Create a test app."""
    project = Project(id=1, name="test_project", active=True)
    app_obj = App(
        id=1,
        project_id=1,
        name="test_app",
        api_key="test_api_key_123",
        active=True,
    )
    app_obj.project = project
    return app_obj


def test_get_app_from_api_key_found(mock_db_session, test_app):
    """Test finding an app by API key."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = test_app
    
    result = get_app_from_api_key("test_api_key_123", mock_db_session)
    
    assert result == test_app


def test_get_app_from_api_key_not_found(mock_db_session):
    """Test not finding an app by API key."""
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    
    result = get_app_from_api_key("invalid_key", mock_db_session)
    
    assert result is None
