"""Checkout API endpoints."""

from datetime import datetime
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from billing_service.auth import verify_project_api_key
from billing_service.database import get_db
from billing_service.models import Price, Project
from billing_service.schemas import CheckoutCreateRequest, CheckoutCreateResponse
from billing_service.stripe_service import create_checkout_session

router = APIRouter(prefix="/api/v1/checkout", tags=["checkout"])


@router.post("/create", response_model=CheckoutCreateResponse)
async def create_checkout(
    request: CheckoutCreateRequest,
    project: Project = Depends(verify_project_api_key),
    db: Session = Depends(get_db),
):
    """Create a Stripe checkout session."""
    # Verify price exists and belongs to project
    price = (
        db.query(Price)
        .join(Price.product)
        .filter(
            Price.id == request.price_id,
            Price.product.has(project_id=project.id),
        )
        .first()
    )

    if not price:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Price not found",
        )

    if price.is_archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Price is archived and cannot be purchased",
        )

    # Create checkout session
    try:
        session = create_checkout_session(
            price_stripe_id=str(price.stripe_price_id),
            user_id=request.user_id,
            project_id=str(project.project_id),
            mode=cast("Literal['subscription', 'payment']", request.mode),
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}",
        ) from e

    return CheckoutCreateResponse(
        checkout_url=session.url or "",
        session_id=session.id,
        expires_at=datetime.fromtimestamp(session.expires_at),
    )
