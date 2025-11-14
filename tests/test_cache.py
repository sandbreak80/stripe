"""Tests for cache functionality."""

import pytest
from unittest.mock import Mock, patch

from billing_service.cache import (
    get_redis_client,
    is_event_processed,
    mark_event_processed,
    cache_entitlements,
    get_cached_entitlements,
    invalidate_entitlements_cache,
)


@patch("billing_service.cache.get_redis_client")
def test_is_event_processed(mock_get_client):
    """Test checking if event is processed."""
    mock_client = Mock()
    mock_get_client.return_value = mock_client
    
    # Event not processed
    mock_client.exists.return_value = False
    assert is_event_processed("evt_123") is False
    
    # Event processed
    mock_client.exists.return_value = True
    assert is_event_processed("evt_123") is True


@patch("billing_service.cache.get_redis_client")
def test_mark_event_processed(mock_get_client):
    """Test marking event as processed."""
    mock_client = Mock()
    mock_get_client.return_value = mock_client
    
    mark_event_processed("evt_456")
    
    mock_client.setex.assert_called_once()
    args = mock_client.setex.call_args[0]
    assert args[0] == "webhook_event:evt_456"


@patch("billing_service.cache.get_redis_client")
def test_cache_entitlements(mock_get_client):
    """Test caching entitlements."""
    mock_client = Mock()
    mock_get_client.return_value = mock_client
    
    entitlements = [{"feature_code": "feature1", "is_active": True}]
    cache_entitlements("user_123", "project_456", entitlements)
    
    mock_client.setex.assert_called_once()
    args = mock_client.setex.call_args[0]
    assert "entitlements:project_456:user_123" in args[0]


@patch("billing_service.cache.get_redis_client")
def test_get_cached_entitlements(mock_get_client):
    """Test retrieving cached entitlements."""
    mock_client = Mock()
    mock_get_client.return_value = mock_client
    
    # Cache hit
    import json
    cached_data = json.dumps([{"feature_code": "feature1"}])
    mock_client.get.return_value = cached_data.encode()
    
    result = get_cached_entitlements("user_123", "project_456")
    assert result == [{"feature_code": "feature1"}]
    
    # Cache miss
    mock_client.get.return_value = None
    result = get_cached_entitlements("user_123", "project_456")
    assert result is None


@patch("billing_service.cache.get_redis_client")
def test_invalidate_entitlements_cache(mock_get_client):
    """Test invalidating entitlements cache."""
    mock_client = Mock()
    mock_get_client.return_value = mock_client
    
    invalidate_entitlements_cache("user_123", "project_456")
    
    mock_client.delete.assert_called_once()
    args = mock_client.delete.call_args[0]
    assert "entitlements:project_456:user_123" in args[0]
