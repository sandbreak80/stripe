"""Test fixtures and utilities."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from billing_service.database import Base, get_db
from billing_service.models import (
    EntitlementSource,
    PriceInterval,
    Project,
    Product,
    Price,
    PurchaseStatus,
    SubscriptionStatus,
)


@pytest.fixture(scope="function")
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def test_project(db_session):
    """Create a test project."""
    import hashlib

    api_key = "test_api_key_123"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    project = Project(
        project_id="test-project",
        name="Test Project",
        description="Test project description",
        api_key_hash=api_key_hash,
        is_active=True,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def test_product(db_session, test_project):
    """Create a test product."""
    product = Product(
        product_id="test-product",
        project_id=test_project.id,
        name="Test Product",
        description="Test product description",
        feature_codes=["feature1", "feature2"],
        is_archived=False,
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


@pytest.fixture
def test_price(db_session, test_product):
    """Create a test price."""
    price = Price(
        stripe_price_id="price_test123",
        product_id=test_product.id,
        amount=999,  # $9.99
        currency="usd",
        interval=PriceInterval.MONTH,
        is_archived=False,
    )
    db_session.add(price)
    db_session.commit()
    db_session.refresh(price)
    return price
