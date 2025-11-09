"""Tests for cache functionality."""

from unittest.mock import MagicMock, patch

import pytest

from billing_service.cache import (
    get_entitlement_cache_key,
    get_entitlements_from_cache,
    get_redis_client,
    invalidate_entitlements_cache,
    set_entitlements_in_cache,
)


def test_get_entitlement_cache_key():
    """Test cache key generation."""
    key = get_entitlement_cache_key(123, 456)
    assert key == "entitlements:user:123:project:456"


@patch("billing_service.cache.get_redis_client")
def test_get_entitlements_from_cache_hit(mock_get_client):
    """Test getting entitlements from cache when present."""
    mock_client = MagicMock()
    mock_client.get.return_value = '[{"feature_code": "premium", "active": true}]'
    mock_get_client.return_value = mock_client
    
    result = get_entitlements_from_cache(1, 1)
    
    assert result is not None
    assert len(result) == 1
    assert result[0]["feature_code"] == "premium"


@patch("billing_service.cache.get_redis_client")
def test_get_entitlements_from_cache_miss(mock_get_client):
    """Test getting entitlements from cache when not present."""
    mock_client = MagicMock()
    mock_client.get.return_value = None
    mock_get_client.return_value = mock_client
    
    result = get_entitlements_from_cache(1, 1)
    
    assert result is None


@patch("billing_service.cache.get_redis_client")
def test_set_entitlements_in_cache(mock_get_client):
    """Test setting entitlements in cache."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    
    entitlements = [{"feature_code": "premium", "active": True}]
    set_entitlements_in_cache(1, 1, entitlements, ttl=3600)
    
    mock_client.setex.assert_called_once()


@patch("billing_service.cache.get_redis_client")
def test_get_entitlements_from_cache_error(mock_get_client):
    """Test getting entitlements from cache when Redis fails."""
    mock_client = MagicMock()
    mock_client.get.side_effect = Exception("Redis error")
    mock_get_client.return_value = mock_client
    
    result = get_entitlements_from_cache(1, 1)
    
    assert result is None


@patch("billing_service.cache.get_redis_client")
def test_set_entitlements_in_cache_error(mock_get_client):
    """Test setting entitlements in cache when Redis fails."""
    mock_client = MagicMock()
    mock_client.setex.side_effect = Exception("Redis error")
    mock_get_client.return_value = mock_client
    
    # Should not raise exception
    entitlements = [{"feature_code": "premium", "active": True}]
    set_entitlements_in_cache(1, 1, entitlements, ttl=3600)


@patch("billing_service.cache.get_redis_client")
def test_invalidate_entitlements_cache_error(mock_get_client):
    """Test invalidating entitlements cache when Redis fails."""
    mock_client = MagicMock()
    mock_client.delete.side_effect = Exception("Redis error")
    mock_get_client.return_value = mock_client
    
    # Should not raise exception
    invalidate_entitlements_cache(1, 1)
