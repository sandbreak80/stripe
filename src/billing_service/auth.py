"""Authentication middleware and utilities."""

import hashlib
import hmac

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from billing_service.database import get_db
from billing_service.models import Project

security = HTTPBearer()


def hash_api_key(api_key: str) -> str:
    """Hash an API key using SHA-256."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(api_key_hash: str, provided_key: str) -> bool:
    """Verify a provided API key against a hash."""
    return hmac.compare_digest(api_key_hash, hash_api_key(provided_key))


async def get_project_from_api_key(
    api_key: str,
    db: Session,
) -> Project | None:
    """Get project from API key."""
    if not api_key:
        return None

    api_key_hash = hash_api_key(api_key)

    # Find project with matching API key hash
    project = db.query(Project).filter(Project.api_key_hash == api_key_hash).first()

    if not project:
        return None

    if not project.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project is not active",
        )

    return project


async def verify_project_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Project:
    """Dependency to verify project API key and return project."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_key = credentials.credentials

    # Get database session
    db_gen = get_db()
    db = next(db_gen)

    try:
        project = await get_project_from_api_key(api_key, db)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return project
    finally:
        db.close()


async def verify_admin_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Dependency to verify admin API key and return admin user identifier."""
    from billing_service.config import settings

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_key = credentials.credentials

    if not settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API not configured",
        )

    if not hmac.compare_digest(settings.admin_api_key, api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Return admin identifier (could be from config or extracted from key)
    return settings.admin_api_key[:8] + "..."  # Simplified identifier
