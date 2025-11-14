"""Redis cache for event deduplication and caching."""

import json
import logging
from datetime import timedelta

import redis
from redis.exceptions import RedisError

from billing_service.config import settings

logger = logging.getLogger(__name__)

# Redis connection pool (singleton)
_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client

    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=False,  # Keep as bytes for binary data
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            # Test connection
            _redis_client.ping()
            logger.info("Redis connection established")
        except RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    return _redis_client


def is_event_processed(event_id: str) -> bool:
    """
    Check if a Stripe event has already been processed.

    Args:
        event_id: Stripe event ID

    Returns:
        True if event was already processed, False otherwise
    """
    try:
        client = get_redis_client()
        key = f"webhook_event:{event_id}"
        exists = client.exists(key)
        return bool(exists)
    except RedisError as e:
        logger.error(f"Redis error checking event: {e}")
        # If Redis fails, assume event not processed (fail open)
        # This allows processing to continue even if Redis is down
        return False


def mark_event_processed(event_id: str, ttl_hours: int = 48) -> None:
    """
    Mark a Stripe event as processed.

    Args:
        event_id: Stripe event ID
        ttl_hours: Time to live in hours (default 48 hours)
    """
    try:
        client = get_redis_client()
        key = f"webhook_event:{event_id}"
        # Store event ID with timestamp
        value = json.dumps({"event_id": event_id, "processed_at": None}).encode()
        client.setex(key, timedelta(hours=ttl_hours), value)
        logger.debug(f"Marked event {event_id} as processed")
    except RedisError as e:
        logger.error(f"Redis error marking event: {e}")
        # Don't raise - event processing should continue even if Redis fails


def cache_entitlements(
    user_id: str,
    project_id: str,
    entitlements: list,
    ttl_seconds: int = 300,
) -> None:
    """
    Cache entitlements for a user in a project.

    Args:
        user_id: User identifier
        project_id: Project identifier
        entitlements: List of entitlement dictionaries
        ttl_seconds: Time to live in seconds (default 5 minutes)
    """
    try:
        client = get_redis_client()
        key = f"entitlements:{project_id}:{user_id}"
        value = json.dumps(entitlements).encode()
        client.setex(key, timedelta(seconds=ttl_seconds), value)
    except RedisError as e:
        logger.warning(f"Redis error caching entitlements: {e}")
        # Don't raise - caching is optional


def get_cached_entitlements(
    user_id: str,
    project_id: str,
) -> list | None:
    """
    Get cached entitlements for a user in a project.

    Args:
        user_id: User identifier
        project_id: Project identifier

    Returns:
        List of entitlements if cached, None otherwise
    """
    try:
        client = get_redis_client()
        key = f"entitlements:{project_id}:{user_id}"
        value = client.get(key)
        if value:
            return json.loads(value.decode())
        return None
    except RedisError as e:
        logger.warning(f"Redis error getting cached entitlements: {e}")
        return None
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning(f"Error decoding cached entitlements: {e}")
        return None


def invalidate_entitlements_cache(user_id: str, project_id: str) -> None:
    """
    Invalidate cached entitlements for a user in a project.

    Args:
        user_id: User identifier
        project_id: Project identifier
    """
    try:
        client = get_redis_client()
        key = f"entitlements:{project_id}:{user_id}"
        client.delete(key)
        logger.debug(f"Invalidated entitlements cache for {user_id} in {project_id}")
    except RedisError as e:
        logger.warning(f"Redis error invalidating cache: {e}")
        # Don't raise - cache invalidation is best-effort
