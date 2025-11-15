"""Helper utilities for test refactoring."""

from sqlalchemy.orm import sessionmaker


def create_session_factory(db_engine):
    """Create a session factory from db_engine for thread-safe testing."""
    TestingSessionLocal = sessionmaker(bind=db_engine)
    
    def create_session():
        return TestingSessionLocal()
    
    return create_session, TestingSessionLocal

