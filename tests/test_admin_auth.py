"""Tests for admin API authentication."""

import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from billing_service.auth import verify_admin_api_key, hash_api_key


@pytest.mark.asyncio
@patch("billing_service.config.settings")
async def test_verify_admin_api_key_success(mock_settings):
    """Test successful admin API key verification."""
    # Create a mock settings object with admin_api_key attribute
    mock_settings.admin_api_key = "admin_key_123"
    
    mock_credentials = Mock(spec=HTTPAuthorizationCredentials)
    mock_credentials.credentials = "admin_key_123"
    
    # Import after patching to ensure the patch is in place
    from billing_service.auth import verify_admin_api_key
    result = await verify_admin_api_key(mock_credentials)
    # admin_key_123[:8] = "admin_ke", so result should be "admin_ke..."
    assert result == "admin_ke..."


@pytest.mark.asyncio
@patch("billing_service.config.settings")
async def test_verify_admin_api_key_invalid(mock_settings):
    """Test admin API key verification with invalid key."""
    mock_settings.admin_api_key = "admin_key_123"
    
    mock_credentials = Mock(spec=HTTPAuthorizationCredentials)
    mock_credentials.credentials = "wrong_key"
    
    with pytest.raises(HTTPException) as exc_info:
        await verify_admin_api_key(mock_credentials)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
@patch("billing_service.config.settings")
async def test_verify_admin_api_key_not_configured(mock_settings):
    """Test admin API key verification when not configured."""
    mock_settings.admin_api_key = None
    
    mock_credentials = Mock(spec=HTTPAuthorizationCredentials)
    mock_credentials.credentials = "any_key"
    
    with pytest.raises(HTTPException) as exc_info:
        await verify_admin_api_key(mock_credentials)
    assert exc_info.value.status_code == 503


def test_hash_api_key():
    """Test API key hashing."""
    key = "test_key_123"
    hash1 = hash_api_key(key)
    hash2 = hash_api_key(key)

    # Same key should produce same hash
    assert hash1 == hash2
    # Hash should be different from original
    assert hash1 != key
    # Hash should be 64 characters (SHA-256 hex)
    assert len(hash1) == 64
