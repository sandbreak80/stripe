"""Pydantic schemas for request/response validation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# Checkout Schemas
class CheckoutCreateRequest(BaseModel):
    """Request schema for creating a checkout session."""

    user_id: str = Field(..., description="User identifier from micro-app")
    price_id: UUID = Field(..., description="Price UUID to purchase")
    mode: str = Field(..., pattern="^(subscription|payment)$", description="Checkout mode")
    success_url: str = Field(..., description="URL to redirect after successful payment")
    cancel_url: str = Field(..., description="URL to redirect if payment is cancelled")


class CheckoutCreateResponse(BaseModel):
    """Response schema for checkout session creation."""

    checkout_url: str = Field(..., description="Stripe checkout URL")
    session_id: str = Field(..., description="Stripe checkout session ID")
    expires_at: datetime = Field(..., description="Session expiration timestamp")


# Entitlements Schemas
class EntitlementResponse(BaseModel):
    """Response schema for a single entitlement."""

    feature_code: str = Field(..., description="Feature identifier")
    is_active: bool = Field(..., description="Whether entitlement is currently active")
    valid_from: datetime = Field(..., description="Access start timestamp")
    valid_to: datetime | None = Field(None, description="Access end timestamp (null = indefinite)")
    source: str = Field(..., description="Source of entitlement: subscription, purchase, or manual")


class EntitlementsQueryResponse(BaseModel):
    """Response schema for entitlements query."""

    user_id: str = Field(..., description="User identifier")
    project_id: str = Field(..., description="Project identifier")
    entitlements: list[EntitlementResponse] = Field(..., description="List of entitlements")
    checked_at: datetime = Field(..., description="Timestamp when entitlements were checked")


# Portal Schemas
class PortalCreateRequest(BaseModel):
    """Request schema for creating a portal session."""

    user_id: str = Field(..., description="User identifier from micro-app")
    return_url: str = Field(..., description="URL to return to after portal session")


class PortalCreateResponse(BaseModel):
    """Response schema for portal session creation."""

    portal_url: str = Field(..., description="Stripe Customer Portal URL")
    expires_at: datetime = Field(..., description="Session expiration timestamp")


# Health Check Schemas
class HealthResponse(BaseModel):
    """Response schema for health check."""

    status: str = Field(..., description="Health status")


# Error Schemas
class ErrorResponse(BaseModel):
    """Response schema for errors."""

    detail: str = Field(..., description="Error message")
