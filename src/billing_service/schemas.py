"""API schemas for request/response models."""


from pydantic import BaseModel


class CheckoutSessionRequest(BaseModel):
    """Request model for checkout session creation."""

    user_id: str
    project_id: int
    price_id: str
    mode: str  # "subscription" or "payment"
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    """Response model for checkout session creation."""

    checkout_url: str


class PortalSessionRequest(BaseModel):
    """Request model for portal session creation."""

    user_id: str
    project_id: int
    return_url: str


class PortalSessionResponse(BaseModel):
    """Response model for portal session creation."""

    portal_url: str
