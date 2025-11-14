"""SQLAlchemy models for billing service."""

import uuid
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class SubscriptionStatus(PyEnum):
    """Subscription status enum."""

    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    UNPAID = "unpaid"


class PurchaseStatus(PyEnum):
    """Purchase status enum."""

    SUCCEEDED = "succeeded"
    PENDING = "pending"
    FAILED = "failed"
    REFUNDED = "refunded"


class PriceInterval(PyEnum):
    """Price interval enum."""

    MONTH = "month"
    YEAR = "year"
    ONE_TIME = "one_time"


class EntitlementSource(PyEnum):
    """Entitlement source enum."""

    SUBSCRIPTION = "subscription"
    PURCHASE = "purchase"
    MANUAL = "manual"


class Project(Base):  # type: ignore[misc,valid-type]
    """Project model - represents a micro-application."""

    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    api_key_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    products = relationship("Product", back_populates="project", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="project")
    purchases = relationship("Purchase", back_populates="project")
    manual_grants = relationship("ManualGrant", back_populates="project")
    entitlements = relationship("Entitlement", back_populates="project")

    __table_args__ = (Index("idx_projects_project_id", "project_id"),)


class Product(Base):  # type: ignore[misc,valid-type]
    """Product model - represents a sellable capability or feature set."""

    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(String(255), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    feature_codes = Column(JSON, nullable=False)  # List of feature codes
    is_archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    project = relationship("Project", back_populates="products")
    prices = relationship("Price", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("product_id", "project_id", name="uq_product_project"),
        Index("idx_products_project_id", "project_id"),
    )


class Price(Base):  # type: ignore[misc,valid-type]
    """Price model - represents a commercial term for a product."""

    __tablename__ = "prices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stripe_price_id = Column(String(255), unique=True, nullable=False, index=True)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)  # Price in cents
    currency = Column(String(3), default="usd", nullable=False)
    interval = Column(Enum(PriceInterval), nullable=False)  # type: ignore[var-annotated]
    is_archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    product = relationship("Product", back_populates="prices")
    subscriptions = relationship("Subscription", back_populates="price")
    purchases = relationship("Purchase", back_populates="price")

    __table_args__ = (Index("idx_prices_product_id", "product_id"),)


class Subscription(Base):  # type: ignore[misc,valid-type]
    """Subscription model - represents a recurring billing arrangement."""

    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stripe_subscription_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    price_id = Column(UUID(as_uuid=True), ForeignKey("prices.id"), nullable=False, index=True)
    status = Column(Enum(SubscriptionStatus), nullable=False, index=True)  # type: ignore[var-annotated]
    current_period_start = Column(DateTime(timezone=True), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    project = relationship("Project", back_populates="subscriptions")
    price = relationship("Price", back_populates="subscriptions")

    __table_args__ = (
        Index("idx_subscriptions_user_project", "user_id", "project_id"),
        Index("idx_subscriptions_status", "status"),
        Index("idx_subscriptions_period_end", "current_period_end"),
    )


class Purchase(Base):  # type: ignore[misc,valid-type]
    """Purchase model - represents a one-time payment."""

    __tablename__ = "purchases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stripe_charge_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    price_id = Column(UUID(as_uuid=True), ForeignKey("prices.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)  # Amount in cents
    currency = Column(String(3), default="usd", nullable=False)
    status = Column(Enum(PurchaseStatus), nullable=False, index=True)  # type: ignore[var-annotated]
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_to = Column(DateTime(timezone=True), nullable=True)  # null = lifetime
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    project = relationship("Project", back_populates="purchases")
    price = relationship("Price", back_populates="purchases")

    __table_args__ = (
        Index("idx_purchases_user_project", "user_id", "project_id"),
        Index("idx_purchases_status", "status"),
        Index("idx_purchases_valid_to", "valid_to"),
    )


class ManualGrant(Base):  # type: ignore[misc,valid-type]
    """ManualGrant model - represents an administrative entitlement grant."""

    __tablename__ = "manual_grants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    feature_code = Column(String(255), nullable=False, index=True)
    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_to = Column(DateTime(timezone=True), nullable=True)  # null = indefinite
    reason = Column(Text, nullable=False)
    granted_by = Column(String(255), nullable=False)
    granted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(String(255), nullable=True)
    revoke_reason = Column(Text, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="manual_grants")

    __table_args__ = (
        Index("idx_manual_grants_user_project", "user_id", "project_id"),
        Index("idx_manual_grants_feature", "feature_code"),
        Index("idx_manual_grants_valid_to", "valid_to"),
    )


class Entitlement(Base):  # type: ignore[misc,valid-type]
    """Entitlement model - represents computed access rights for a user."""

    __tablename__ = "entitlements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    feature_code = Column(String(255), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, index=True)
    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_to = Column(DateTime(timezone=True), nullable=True)  # null = indefinite
    source = Column(Enum(EntitlementSource), nullable=False)  # type: ignore[var-annotated]
    source_id = Column(UUID(as_uuid=True), nullable=False)  # ID of subscription/purchase/grant
    computed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="entitlements")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "project_id", "feature_code", "source", "source_id", name="uq_entitlement"
        ),
        Index("idx_entitlements_user_project", "user_id", "project_id"),
        Index("idx_entitlements_feature", "feature_code"),
        Index("idx_entitlements_active", "is_active"),
        Index("idx_entitlements_valid_to", "valid_to"),
    )
