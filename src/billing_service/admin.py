"""Administrative API endpoints."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from billing_service.auth import verify_api_key
from billing_service.cache import invalidate_entitlements_cache
from billing_service.database import get_db
from billing_service.entitlements import recompute_and_store_entitlements
from billing_service.models import App, ManualGrant, User

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class GrantRequest(BaseModel):
    """Request model for grant endpoint."""

    user_id: str
    project_id: int
    feature_code: str
    granted_by: str
    reason: Any | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None


class RevokeRequest(BaseModel):
    """Request model for revoke endpoint."""

    user_id: str
    project_id: int
    feature_code: str
    granted_by: str
    reason: Any | None = None


@router.post("/grant")
async def grant_entitlement(
    request: GrantRequest,
    app: App = Depends(verify_api_key),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Manually grant an entitlement."""
    # Verify project access
    if app.project_id != request.project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this project",
        )

    # Find user
    user = (
        db.query(User)
        .filter(
            User.external_user_id == request.user_id,
            User.project_id == request.project_id,
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Create manual grant record
    grant = ManualGrant(
        user_id=user.id,
        project_id=request.project_id,
        feature_code=request.feature_code,
        action="grant",
        granted_by=request.granted_by,
        reason=request.reason,
        valid_from=request.valid_from or datetime.utcnow(),
        valid_to=request.valid_to,
    )
    db.add(grant)
    db.commit()

    # Recompute entitlements
    recompute_and_store_entitlements(user.id, request.project_id, db)  # type: ignore[arg-type]

    # Invalidate cache
    invalidate_entitlements_cache(user.id, request.project_id)  # type: ignore[arg-type]

    return {"status": "granted", "message": "Entitlement granted successfully"}


@router.post("/revoke")
async def revoke_entitlement(
    request: RevokeRequest,
    app: App = Depends(verify_api_key),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Manually revoke an entitlement."""
    # Verify project access
    if app.project_id != request.project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this project",
        )

    # Find user
    user = (
        db.query(User)
        .filter(
            User.external_user_id == request.user_id,
            User.project_id == request.project_id,
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Create manual revoke record
    revoke = ManualGrant(
        user_id=user.id,
        project_id=request.project_id,
        feature_code=request.feature_code,
        action="revoke",
        granted_by=request.granted_by,
        reason=request.reason,
    )
    db.add(revoke)
    db.commit()

    # Recompute entitlements
    recompute_and_store_entitlements(user.id, request.project_id, db)  # type: ignore[arg-type]

    # Invalidate cache
    invalidate_entitlements_cache(user.id, request.project_id)  # type: ignore[arg-type]

    return {"status": "revoked", "message": "Entitlement revoked successfully"}
