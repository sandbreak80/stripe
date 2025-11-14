"""Entitlements API endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from billing_service.auth import verify_project_api_key
from billing_service.cache import (
    cache_entitlements,
    get_cached_entitlements,
)
from billing_service.database import get_db
from billing_service.models import Entitlement, Project
from billing_service.schemas import EntitlementResponse, EntitlementsQueryResponse

router = APIRouter(prefix="/api/v1/entitlements", tags=["entitlements"])


@router.get("", response_model=EntitlementsQueryResponse)
async def get_entitlements(
    user_id: str = Query(..., description="User identifier"),
    project: Project = Depends(verify_project_api_key),
    db: Session = Depends(get_db),
):
    """Get entitlements for a user in a project."""
    # Try to get from cache first
    cache_key_project_id = str(project.project_id)
    cached_data = get_cached_entitlements(user_id, cache_key_project_id)

    if cached_data:
        # Return cached entitlements
        entitlement_responses = [
            EntitlementResponse(
                feature_code=ent["feature_code"],
                is_active=ent["is_active"],
                valid_from=datetime.fromisoformat(ent["valid_from"]) if isinstance(ent["valid_from"], str) else ent["valid_from"],
                valid_to=datetime.fromisoformat(ent["valid_to"]) if ent.get("valid_to") and isinstance(ent["valid_to"], str) else ent.get("valid_to"),
                source=ent["source"],
            )
            for ent in cached_data
        ]

        return EntitlementsQueryResponse(
            user_id=user_id,
            project_id=cache_key_project_id,
            entitlements=entitlement_responses,
            checked_at=datetime.utcnow(),
        )

    # Cache miss - query database
    entitlements = (
        db.query(Entitlement)
        .filter(
            Entitlement.user_id == user_id,
            Entitlement.project_id == project.id,
            Entitlement.is_active == True,  # noqa: E712
        )
        .all()
    )

    # Convert to response format
    entitlement_responses = [
        EntitlementResponse(
            feature_code=str(ent.feature_code),
            is_active=bool(ent.is_active),
            valid_from=ent.valid_from,  # type: ignore
            valid_to=ent.valid_to,  # type: ignore
            source=str(ent.source.value),
        )
        for ent in entitlements
    ]

    # Cache the results for 5 minutes (300 seconds)
    cache_data = [
        {
            "feature_code": str(ent.feature_code),
            "is_active": bool(ent.is_active),
            "valid_from": ent.valid_from.isoformat() if ent.valid_from else None,  # type: ignore
            "valid_to": ent.valid_to.isoformat() if ent.valid_to else None,  # type: ignore
            "source": str(ent.source.value),
        }
        for ent in entitlements
    ]
    cache_entitlements(user_id, cache_key_project_id, cache_data, ttl_seconds=300)

    return EntitlementsQueryResponse(
        user_id=user_id,
        project_id=cache_key_project_id,
        entitlements=entitlement_responses,
        checked_at=datetime.utcnow(),
    )
