"""Tests for authentication."""

import hashlib

import pytest

from billing_service.auth import hash_api_key, verify_api_key, get_project_from_api_key
from billing_service.models import Project


def test_hash_api_key():
    """Test API key hashing."""
    api_key = "test_key_123"
    hashed = hash_api_key(api_key)
    
    # Should produce consistent hash
    assert hashed == hash_api_key(api_key)
    
    # Should be different for different keys
    assert hashed != hash_api_key("different_key")


def test_verify_api_key():
    """Test API key verification."""
    api_key = "test_key_456"
    hashed = hash_api_key(api_key)
    
    # verify_api_key takes (api_key_hash, provided_key)
    assert verify_api_key(hashed, api_key) is True
    assert verify_api_key(hashed, "wrong_key") is False


@pytest.mark.asyncio
async def test_get_project_from_api_key(db_session):
    """Test retrieving project from API key."""
    api_key = "test_api_key_789"
    api_key_hash = hash_api_key(api_key)
    
    project = Project(
        project_id="test-project-auth",
        name="Test Project Auth",
        api_key_hash=api_key_hash,
        is_active=True,
    )
    db_session.add(project)
    db_session.commit()
    
    # Should find project with correct key
    found = await get_project_from_api_key(api_key, db_session)
    assert found is not None
    assert found.project_id == "test-project-auth"
    
    # Should not find project with wrong key
    not_found = await get_project_from_api_key("wrong_key", db_session)
    assert not_found is None
    
    # Should not find inactive project
    project.is_active = False
    db_session.commit()
    not_found_inactive = await get_project_from_api_key(api_key, db_session)
    assert not_found_inactive is None
