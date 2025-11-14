"""Admin API endpoints for manual entitlement management."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from billing_service.auth import verify_admin_api_key
from billing_service.database import get_db
from billing_service.entitlements import recompute_and_store_entitlements
from billing_service.models import ManualGrant, Project
from billing_service.reconciliation import reconcile_all

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class GrantCreateRequest(BaseModel):
    """Request schema for creating a manual grant."""

    user_id: str = Field(..., description="User identifier")
    project_id: str = Field(..., description="Project identifier")
    feature_code: str = Field(..., description="Feature code to grant")
    valid_from: datetime | None = Field(None, description="Access start timestamp (defaults to now)")
    valid_to: datetime | None = Field(None, description="Access end timestamp (null = indefinite)")
    reason: str = Field(..., description="Reason for grant (required for audit trail)")


class GrantCreateResponse(BaseModel):
    """Response schema for grant creation."""

    grant_id: UUID = Field(..., description="Grant UUID")
    user_id: str = Field(..., description="User identifier")
    project_id: str = Field(..., description="Project identifier")
    feature_code: str = Field(..., description="Feature code")
    valid_from: datetime = Field(..., description="Access start timestamp")
    valid_to: datetime | None = Field(None, description="Access end timestamp")
    granted_at: datetime = Field(..., description="Grant creation timestamp")


class RevokeRequest(BaseModel):
    """Request schema for revoking a grant."""

    grant_id: UUID = Field(..., description="Grant UUID to revoke")
    revoke_reason: str = Field(..., description="Reason for revocation (required for audit trail)")


class RevokeResponse(BaseModel):
    """Response schema for grant revocation."""

    grant_id: UUID = Field(..., description="Grant UUID")
    revoked_at: datetime = Field(..., description="Revocation timestamp")


@router.post("/grant", response_model=GrantCreateResponse)
async def create_grant(
    request: GrantCreateRequest,
    admin_user: str = Depends(verify_admin_api_key),
    db: Session = Depends(get_db),
) -> GrantCreateResponse:
    """
    Create a manual entitlement grant.

    Requires admin API key authentication.
    """
    if not request.reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reason is required for manual grants",
        )

    # Find project
    project = db.query(Project).filter(Project.project_id == request.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {request.project_id}",
        )

    # Check if grant already exists and is active
    existing = (
        db.query(ManualGrant)
        .filter(
            ManualGrant.user_id == request.user_id,
            ManualGrant.project_id == project.id,
            ManualGrant.feature_code == request.feature_code,
            ManualGrant.revoked_at.is_(None),
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Active grant already exists for this user/feature",
        )

    # Create grant
    grant = ManualGrant(
        user_id=request.user_id,
        project_id=project.id,
        feature_code=request.feature_code,
        valid_from=request.valid_from or datetime.utcnow(),
        valid_to=request.valid_to,
        reason=request.reason,
        granted_by=admin_user,
        granted_at=datetime.utcnow(),
    )

    db.add(grant)
    db.commit()
    db.refresh(grant)

    # Recompute entitlements
    recompute_and_store_entitlements(db, request.user_id, project.id)  # type: ignore[arg-type]

    return GrantCreateResponse(
        grant_id=grant.id,  # type: ignore[arg-type]
        user_id=request.user_id,
        project_id=request.project_id,
        feature_code=request.feature_code,
        valid_from=grant.valid_from,  # type: ignore[arg-type]
        valid_to=grant.valid_to,  # type: ignore[arg-type]
        granted_at=grant.granted_at,  # type: ignore[arg-type]
    )


@router.post("/revoke", response_model=RevokeResponse)
async def revoke_grant(
    request: RevokeRequest,
    admin_user: str = Depends(verify_admin_api_key),
    db: Session = Depends(get_db),
) -> RevokeResponse:
    """
    Revoke a manual entitlement grant.

    Requires admin API key authentication.
    """
    if not request.revoke_reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Revoke reason is required",
        )

    # Find grant
    grant = db.query(ManualGrant).filter(ManualGrant.id == request.grant_id).first()
    if not grant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grant not found: {request.grant_id}",
        )

    if grant.revoked_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Grant is already revoked",
        )

    # Revoke grant
    grant.revoked_at = datetime.utcnow()  # type: ignore[assignment]
    grant.revoked_by = admin_user  # type: ignore[assignment]
    grant.revoke_reason = request.revoke_reason  # type: ignore[assignment]

    db.commit()
    db.refresh(grant)

    # Recompute entitlements
    recompute_and_store_entitlements(db, grant.user_id, grant.project_id)  # type: ignore[arg-type]

    return RevokeResponse(
        grant_id=grant.id,  # type: ignore[arg-type]
        revoked_at=grant.revoked_at,  # type: ignore[arg-type]
    )


class ReconciliationResponse(BaseModel):
    """Response schema for reconciliation operation."""

    subscriptions_synced: int = Field(..., description="Number of subscriptions synced")
    subscriptions_updated: int = Field(..., description="Number of subscriptions updated")
    subscriptions_missing_in_stripe: int = Field(..., description="Number of subscriptions missing in Stripe")
    purchases_synced: int = Field(..., description="Number of purchases synced")
    purchases_updated: int = Field(..., description="Number of purchases updated")
    purchases_missing_in_stripe: int = Field(..., description="Number of purchases missing in Stripe")
    errors: list[str] = Field(default_factory=list, description="List of errors encountered")


@router.post("/reconcile", response_model=ReconciliationResponse)
async def trigger_reconciliation(
    admin_user: str = Depends(verify_admin_api_key),
) -> ReconciliationResponse:
    """
    Manually trigger reconciliation with Stripe.

    Requires admin API key authentication.
    This endpoint can be called manually or by a cron job.
    """
    result = reconcile_all()

    return ReconciliationResponse(
        subscriptions_synced=result.subscriptions_synced,
        subscriptions_updated=result.subscriptions_updated,
        subscriptions_missing_in_stripe=result.subscriptions_missing_in_stripe,
        purchases_synced=result.purchases_synced,
        purchases_updated=result.purchases_updated,
        purchases_missing_in_stripe=result.purchases_missing_in_stripe,
        errors=result.errors,
    )
