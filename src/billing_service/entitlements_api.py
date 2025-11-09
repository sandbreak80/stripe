"""Entitlements API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from billing_service.auth import verify_api_key
from billing_service.cache import (
    get_entitlements_from_cache,
    set_entitlements_in_cache,
)
from billing_service.database import get_db
from billing_service.entitlements import compute_entitlements
from billing_service.models import App, User

router = APIRouter(prefix="/api/v1", tags=["entitlements"])


@router.get("/entitlements")
async def get_entitlements(
    user_id: str,
    project_id: int,
    app: App = Depends(verify_api_key),
    db: Session = Depends(get_db),
) -> dict[str, list[dict[str, str | int | None]]]:
    """Get user entitlements for a project."""
    # Verify project access
    if app.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this project",
        )

    # Find user
    user = (
        db.query(User)
        .filter(User.external_user_id == user_id, User.project_id == project_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Try cache first
    cached = get_entitlements_from_cache(user.id, project_id)  # type: ignore[arg-type]
    if cached:
        return {"entitlements": cached}

    # Compute entitlements
    entitlements = compute_entitlements(user.id, project_id, db)  # type: ignore[arg-type]

    # Convert datetime objects to ISO strings for JSON serialization
    result = []
    for ent in entitlements:
        valid_from_str = (
            ent["valid_from"].isoformat()
            if hasattr(ent["valid_from"], "isoformat")
            else str(ent["valid_from"])
        )
        valid_to_str = None
        if ent["valid_to"]:
            valid_to_str = (
                ent["valid_to"].isoformat()
                if hasattr(ent["valid_to"], "isoformat")
                else str(ent["valid_to"])
            )

        result.append(
            {
                "feature_code": ent["feature_code"],
                "active": ent["active"],
                "source": ent["source"],
                "source_id": ent.get("source_id"),  # Handle cached entries that might not have it
                "valid_from": valid_from_str,
                "valid_to": valid_to_str,
            }
        )

    # Cache the result
    set_entitlements_in_cache(user.id, project_id, result)  # type: ignore[arg-type]

    return {"entitlements": result}
