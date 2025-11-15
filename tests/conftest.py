"""Test fixtures and utilities."""

import pytest
import pytest_asyncio
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

# Import Stripe integration fixtures if available
# These will only be active when USE_REAL_STRIPE is set
try:
    from .conftest_stripe import *  # noqa: F401, F403
except ImportError:
    pass


@pytest_asyncio.fixture
async def client():
    """Create async test client for FastAPI tests."""
    import httpx
    from httpx import ASGITransport
    from billing_service.main import app
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# Global test database engine (thread-safe with SQLite)
_test_engine = None
_test_session_factory = None


@pytest.fixture(scope="session")
def db_engine():
    """Create a test database engine (session-scoped for thread safety)."""
    global _test_engine, _test_session_factory
    
    if _test_engine is None:
        # Use check_same_thread=False to allow SQLite to work across threads (for AsyncClient tests)
        # Note: This is safe for tests but should not be used in production
        _test_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
            poolclass=None,  # Use StaticPool for in-memory SQLite
        )
        Base.metadata.create_all(_test_engine)
        _test_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
    
    return _test_engine


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a test database session (function-scoped, thread-safe)."""
    # Create a new session for each test from the shared engine
    # This ensures thread safety when AsyncClient runs in different threads
    session = _test_session_factory()
    try:
        # Ensure clean state for each test
        yield session
        session.rollback()  # Rollback any uncommitted changes
    finally:
        session.close()


@pytest.fixture
def test_project(db_engine):
    """Create a test project."""
    import hashlib
    from sqlalchemy.orm import sessionmaker
    
    TestingSessionLocal = sessionmaker(bind=db_engine)
    db_session = TestingSessionLocal()
    
    try:
        api_key = "test_api_key_123"
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Check if project already exists to avoid UNIQUE constraint violations
        existing_project = db_session.query(Project).filter(Project.project_id == "test-project").first()
        if existing_project:
            # Update existing project
            existing_project.api_key_hash = api_key_hash
            existing_project.is_active = True
            db_session.commit()
            db_session.refresh(existing_project)
            return existing_project

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
    finally:
        db_session.close()


@pytest.fixture
def test_product(db_engine, test_project):
    """Create a test product."""
    from sqlalchemy.orm import sessionmaker
    
    TestingSessionLocal = sessionmaker(bind=db_engine)
    db_session = TestingSessionLocal()
    
    try:
        # Check if product already exists to avoid UNIQUE constraint violations
        existing_product = db_session.query(Product).filter(
            Product.product_id == "test-product",
            Product.project_id == test_project.id
        ).first()
        if existing_product:
            # Update existing product
            existing_product.is_archived = False
            db_session.commit()
            db_session.refresh(existing_product)
            return existing_product

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
    finally:
        db_session.close()


@pytest.fixture
def test_price(db_engine, test_product):
    """Create a test price."""
    from sqlalchemy.orm import sessionmaker
    
    TestingSessionLocal = sessionmaker(bind=db_engine)
    db_session = TestingSessionLocal()
    
    try:
        # Check if price already exists to avoid UNIQUE constraint violations
        existing_price = db_session.query(Price).filter(
            Price.stripe_price_id == "price_test123",
            Price.product_id == test_product.id
        ).first()
        if existing_price:
            # Update existing price
            existing_price.is_archived = False
            db_session.commit()
            db_session.refresh(existing_price)
            return existing_price

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
    finally:
        db_session.close()
