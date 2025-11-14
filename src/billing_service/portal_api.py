"""Portal API endpoints."""

from datetime import datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from billing_service.auth import verify_project_api_key
from billing_service.config import settings
from billing_service.database import get_db
from billing_service.models import Project, Subscription
from billing_service.schemas import PortalCreateRequest, PortalCreateResponse
from billing_service.stripe_service import create_portal_session as create_stripe_portal_session

router = APIRouter(prefix="/api/v1/portal", tags=["portal"])


@router.post("/create-session", response_model=PortalCreateResponse)
async def create_portal_session_endpoint(
    request: PortalCreateRequest,
    project: Project = Depends(verify_project_api_key),
    db: Session = Depends(get_db),
):
    """Create a Stripe Customer Portal session."""
    # Find user's active subscription to get Stripe customer ID
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == request.user_id,
            Subscription.project_id == project.id,
            Subscription.status.in_(["active", "trialing", "past_due"]),
        )
        .first()
    )

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found for user",
        )

    # Get Stripe customer ID from subscription
    stripe.api_key = settings.stripe_secret_key

    try:
        stripe_subscription = stripe.Subscription.retrieve(str(subscription.stripe_subscription_id))
        customer_id = str(stripe_subscription.customer)

        # Create portal session
        session = create_stripe_portal_session(
            customer_id=customer_id,
            return_url=request.return_url,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create portal session: {str(e)}",
        ) from e

    return PortalCreateResponse(
        portal_url=session.url,
        expires_at=datetime.fromtimestamp(getattr(session, "expires_at", 0)),
    )
