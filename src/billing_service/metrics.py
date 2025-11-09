"""Metrics API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from billing_service.auth import verify_api_key
from billing_service.database import get_db
from billing_service.models import App, Purchase, Subscription

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


@router.get("/project/{project_id}/subscriptions")
async def get_project_subscriptions(
    project_id: int,
    app: App = Depends(verify_api_key),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Get active subscription count for a project."""
    # Verify project access
    if app.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this project",
        )

    # Count active subscriptions
    active_count = (
        db.query(func.count(Subscription.id))
        .filter(
            Subscription.project_id == project_id,
            Subscription.status.in_(["trialing", "active"]),
        )
        .scalar()
        or 0
    )

    total_count = (
        db.query(func.count(Subscription.id)).filter(Subscription.project_id == project_id).scalar()
        or 0
    )

    return {
        "project_id": project_id,
        "active_subscriptions": active_count,
        "total_subscriptions": total_count,
    }


@router.get("/project/{project_id}/revenue")
async def get_project_revenue(
    project_id: int,
    app: App = Depends(verify_api_key),
    db: Session = Depends(get_db),
) -> dict[str, int | str]:
    """Get revenue indicators for a project."""
    # Verify project access
    if app.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this project",
        )

    # Calculate revenue from successful purchases
    revenue = (
        db.query(func.sum(Purchase.amount))
        .filter(
            Purchase.project_id == project_id,
            Purchase.status == "succeeded",
        )
        .scalar()
        or 0
    )

    # Count successful purchases
    purchase_count = (
        db.query(func.count(Purchase.id))
        .filter(
            Purchase.project_id == project_id,
            Purchase.status == "succeeded",
        )
        .scalar()
        or 0
    )

    return {
        "project_id": project_id,
        "total_revenue_cents": revenue,
        "successful_purchases": purchase_count,
    }
