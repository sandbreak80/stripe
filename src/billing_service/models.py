"""Database models."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from billing_service.database import Base


class Project(Base):
    """Project model representing a micro-application."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    apps = relationship("App", back_populates="project")
    users = relationship("User", back_populates="project")
    products = relationship("Product", back_populates="project")


class App(Base):
    """App model representing client integrations."""

    __tablename__ = "apps"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=False, unique=True, index=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="apps")


class User(Base):
    """User model representing end users."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    external_user_id = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="users")
    stripe_customer = relationship("StripeCustomer", back_populates="user", uselist=False)
    purchases = relationship("Purchase", back_populates="user")
    subscriptions = relationship("Subscription", back_populates="user")
    entitlements = relationship("Entitlement", back_populates="user")
    manual_grants = relationship("ManualGrant", back_populates="user")

    # Unique constraint on project_id + external_user_id will be added in migration


class StripeCustomer(Base):
    """Stripe customer mapping."""

    __tablename__ = "stripe_customers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    stripe_customer_id = Column(String(255), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="stripe_customer")


class Purchase(Base):
    """One-time purchase record."""

    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    stripe_payment_intent_id = Column(String(255), nullable=False, unique=True, index=True)
    stripe_price_id = Column(String(255), nullable=False)
    amount = Column(Integer, nullable=False)  # Amount in cents
    currency = Column(String(3), default="usd", nullable=False)
    status = Column(String(50), nullable=False, index=True)  # succeeded, failed, refunded
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="purchases")
    project = relationship("Project")


class Subscription(Base):
    """Subscription record."""

    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    stripe_subscription_id = Column(String(255), nullable=False, unique=True, index=True)
    stripe_price_id = Column(String(255), nullable=False)
    status = Column(
        String(50), nullable=False, index=True
    )  # trialing, active, past_due, canceled, etc.
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True, index=True)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="subscriptions")
    project = relationship("Project")


class WebhookEvent(Base):
    """Raw webhook event storage for idempotency and audit."""

    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    stripe_event_id = Column(String(255), nullable=False, unique=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    processed = Column(Boolean, default=False, nullable=False, index=True)
    raw_payload = Column(Text, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Product(Base):
    """Product model representing catalog items."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="products")
    prices = relationship("Price", back_populates="product")


class Price(Base):
    """Price model with feature code metadata."""

    __tablename__ = "prices"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    stripe_price_id = Column(String(255), nullable=False, unique=True, index=True)
    feature_code = Column(String(100), nullable=False, index=True)  # Links to entitlements
    amount = Column(Integer, nullable=False)  # Amount in cents
    currency = Column(String(3), default="usd", nullable=False)
    interval = Column(String(20), nullable=True)  # month, year, one_time
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    product = relationship("Product", back_populates="prices")


class Entitlement(Base):
    """Entitlement record with validity windows."""

    __tablename__ = "entitlements"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    feature_code = Column(String(100), nullable=False, index=True)
    source = Column(String(50), nullable=False, index=True)  # subscription, purchase, manual
    source_id = Column(Integer, nullable=True)  # ID of subscription, purchase, or manual grant
    active = Column(Boolean, default=True, nullable=False, index=True)
    valid_from = Column(DateTime, nullable=False, index=True)
    valid_to = Column(DateTime, nullable=True, index=True)  # None for lifetime access
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="entitlements")
    project = relationship("Project")


class ManualGrant(Base):
    """Manual entitlement grant/revoke with audit trail."""

    __tablename__ = "manual_grants"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    feature_code = Column(String(100), nullable=False, index=True)
    action = Column(String(20), nullable=False, index=True)  # grant, revoke
    granted_by = Column(String(255), nullable=False)  # Admin identifier
    reason = Column(Text, nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="manual_grants")
    project = relationship("Project")
