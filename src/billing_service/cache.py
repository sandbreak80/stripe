"""Redis cache client for entitlements."""

import json
from typing import Any

import redis

from billing_service.config import settings

# Global Redis client instance
_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def get_entitlement_cache_key(user_id: int, project_id: int) -> str:
    """Generate cache key for user entitlements."""
    return f"entitlements:user:{user_id}:project:{project_id}"


def get_entitlements_from_cache(user_id: int, project_id: int) -> list[dict[str, Any]] | None:
    """Retrieve entitlements from cache."""
    try:
        client = get_redis_client()
        key = get_entitlement_cache_key(user_id, project_id)
        cached = client.get(key)
        if cached:
            return json.loads(cached)  # type: ignore[no-any-return]
    except Exception:
        # Cache failures should not break the application
        pass
    return None


def set_entitlements_in_cache(
    user_id: int, project_id: int, entitlements: list[dict[str, Any]], ttl: int = 3600
) -> None:
    """Store entitlements in cache with TTL."""
    try:
        client = get_redis_client()
        key = get_entitlement_cache_key(user_id, project_id)
        client.setex(key, ttl, json.dumps(entitlements))
    except Exception:
        # Cache failures should not break the application
        pass


def invalidate_entitlements_cache(user_id: int, project_id: int) -> None:
    """Invalidate entitlements cache for a user."""
    try:
        client = get_redis_client()
        key = get_entitlement_cache_key(user_id, project_id)
        client.delete(key)
    except Exception:
        # Cache failures should not break the application
        pass
