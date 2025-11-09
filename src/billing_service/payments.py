"""Payment endpoints for checkout and portal sessions."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from billing_service.auth import verify_api_key
from billing_service.database import get_db
from billing_service.models import App, Project, StripeCustomer, User
from billing_service.schemas import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    PortalSessionRequest,
    PortalSessionResponse,
)
from billing_service.stripe_service import (
    create_checkout_session,
    create_portal_session,
    get_or_create_stripe_customer,
)

router = APIRouter(prefix="/api/v1", tags=["payments"])


@router.post("/checkout/session", response_model=CheckoutSessionResponse)
async def create_checkout_session_endpoint(
    request: CheckoutSessionRequest,
    app: App = Depends(verify_api_key),
    db: Session = Depends(get_db),
) -> CheckoutSessionResponse:
    """Create a Stripe checkout session."""
    # Verify project_id matches app's project
    if request.project_id != app.project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project ID does not match app's project",
        )

    # Get or create user
    user = (
        db.query(User)
        .filter(
            User.project_id == request.project_id,
            User.external_user_id == request.user_id,
        )
        .first()
    )

    if not user:
        # Create user if it doesn't exist
        project = db.query(Project).filter(Project.id == request.project_id).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found",
            )
        user = User(
            project_id=request.project_id,
            external_user_id=request.user_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Get or create Stripe customer
    stripe_customer = get_or_create_stripe_customer(db, user)

    # Create checkout session
    checkout_url = create_checkout_session(
        db=db,
        stripe_customer_id=str(stripe_customer.stripe_customer_id),
        price_id=request.price_id,
        mode=request.mode,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
        project_id=request.project_id,
    )

    return CheckoutSessionResponse(checkout_url=checkout_url)


@router.post("/portal/session", response_model=PortalSessionResponse)
async def create_portal_session_endpoint(
    request: PortalSessionRequest,
    app: App = Depends(verify_api_key),
    db: Session = Depends(get_db),
) -> PortalSessionResponse:
    """Create a Stripe customer portal session."""
    # Verify project access
    if app.project_id != request.project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this project",
        )

    # Get user
    user = (
        db.query(User)
        .filter(
            User.project_id == request.project_id,
            User.external_user_id == request.user_id,
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Get Stripe customer
    stripe_customer = db.query(StripeCustomer).filter(StripeCustomer.user_id == user.id).first()

    if not stripe_customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stripe customer not found. User must have completed at least one purchase.",
        )

    # Create portal session
    portal_url = create_portal_session(
        stripe_customer_id=str(stripe_customer.stripe_customer_id),
        return_url=request.return_url,
    )

    return PortalSessionResponse(portal_url=portal_url)
