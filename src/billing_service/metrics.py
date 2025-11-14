"""Metrics endpoints for project-level subscription and revenue data."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from billing_service.auth import verify_project_api_key
from billing_service.database import get_db
from billing_service.models import Price, PriceInterval, Project, Subscription, SubscriptionStatus

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


class ProjectMetricsResponse(BaseModel):
    """Response schema for project metrics."""

    project_id: str = Field(..., description="Project identifier")
    active_subscriptions: int = Field(..., description="Number of active subscriptions")
    trialing_subscriptions: int = Field(..., description="Number of trialing subscriptions")
    total_subscriptions: int = Field(..., description="Total number of subscriptions")
    estimated_mrr_cents: int = Field(..., description="Estimated Monthly Recurring Revenue in cents")
    estimated_mrr_dollars: float = Field(..., description="Estimated MRR in dollars")


@router.get("/project/{project_id}", response_model=ProjectMetricsResponse)
async def get_project_metrics(
    project_id: str,
    project: Project = Depends(verify_project_api_key),
    db: Session = Depends(get_db),
) -> ProjectMetricsResponse:
    """
    Get metrics for a project.

    Requires project API key authentication. The project_id in the path must match
    the authenticated project.
    """
    # Verify project_id matches authenticated project
    if project.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project ID does not match authenticated project",
        )

    # Count active subscriptions
    active_count = (
        db.query(Subscription)
        .join(Price, Subscription.price_id == Price.id)
        .filter(
            Subscription.project_id == project.id,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        .count()
    )

    # Count trialing subscriptions
    trialing_count = (
        db.query(Subscription)
        .join(Price, Subscription.price_id == Price.id)
        .filter(
            Subscription.project_id == project.id,
            Subscription.status == SubscriptionStatus.TRIALING,
        )
        .count()
    )

    # Total subscriptions
    total_count = (
        db.query(Subscription)
        .filter(Subscription.project_id == project.id)
        .count()
    )

    # Calculate estimated MRR (only from active subscriptions with monthly/yearly intervals)
    # First get monthly subscriptions
    monthly_mrr = (
        db.query(func.sum(Price.amount))
        .join(Subscription, Price.id == Subscription.price_id)
        .filter(
            Subscription.project_id == project.id,
            Subscription.status == SubscriptionStatus.ACTIVE,
            Price.interval == PriceInterval.MONTH,
        )
        .scalar()
    )

    estimated_mrr_cents = int(monthly_mrr) if monthly_mrr else 0

    # Convert yearly subscriptions to monthly equivalent
    yearly_mrr = (
        db.query(func.sum(Price.amount))
        .join(Subscription, Price.id == Subscription.price_id)
        .filter(
            Subscription.project_id == project.id,
            Subscription.status == SubscriptionStatus.ACTIVE,
            Price.interval == PriceInterval.YEAR,
        )
        .scalar()
    )

    if yearly_mrr:
        # Convert yearly to monthly (divide by 12)
        estimated_mrr_cents += int(yearly_mrr / 12)

    estimated_mrr_dollars = estimated_mrr_cents / 100.0

    return ProjectMetricsResponse(
        project_id=project_id,
        active_subscriptions=active_count,
        trialing_subscriptions=trialing_count,
        total_subscriptions=total_count,
        estimated_mrr_cents=estimated_mrr_cents,
        estimated_mrr_dollars=estimated_mrr_dollars,
    )
