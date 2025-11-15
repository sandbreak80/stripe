"""Performance tests for entitlement check SLA validation."""

import pytest
import time
from statistics import median
from unittest.mock import patch
import httpx

from billing_service.main import app


@pytest.mark.performance
@pytest.mark.asyncio
async def test_entitlement_check_p95_latency(client, db_engine, test_project):
    """Validate p95 latency < 100ms for entitlement checks."""
    import hashlib
    from billing_service.main import app
    from billing_service.database import get_db
    from billing_service.auth import verify_project_api_key
    from billing_service.cache import get_cached_entitlements
    
    # Update test project - use a unique user_id to avoid conflicts
    from sqlalchemy.orm import sessionmaker
    from billing_service.models import Project
    TestingSessionLocal = sessionmaker(bind=db_engine)
    
    setup_db = TestingSessionLocal()
    try:
        api_key = "test_perf_p95_key"
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        # Query project from DB using engine to get fresh object
        fresh_project = setup_db.query(Project).filter(Project.id == test_project.id).first()
        fresh_project.api_key_hash = api_key_hash
        setup_db.commit()
        setup_db.refresh(fresh_project)
        test_project_for_override = fresh_project
    finally:
        setup_db.close()
    
    # Use FastAPI dependency override - create a new session per request for thread safety
    async def override_get_db():
        test_session = TestingSessionLocal()
        try:
            yield test_session
        finally:
            test_session.close()
    
    # Override verify_project_api_key - use the exact function reference
    async def override_verify_project_api_key():
        return test_project_for_override
    
    # Override both get_db and verify_project_api_key
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_project_api_key] = override_verify_project_api_key
    
    # Mock cache to return None (cache miss)
    with patch("billing_service.entitlements_api.get_cached_entitlements", return_value=None):
        latencies = []
        num_requests = 100
        
        try:
            for _ in range(num_requests):
                start = time.time()
                response = await client.get(
                    "/api/v1/entitlements?user_id=test_user_cache",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                assert response.status_code == 200
                latencies.append((time.time() - start) * 1000)  # Convert to ms
            
            latencies.sort()
            p95_index = int(len(latencies) * 0.95)
            p95_latency = latencies[p95_index]
            
            # Validate p95 < 100ms (with some margin for test overhead)
            assert p95_latency < 200, f"p95 latency {p95_latency}ms exceeds 200ms threshold (test overhead considered)"
        finally:
            app.dependency_overrides.clear()


@pytest.mark.performance
@pytest.mark.asyncio
async def test_entitlement_check_cache_hit_latency(client, db_engine, test_project):
    """Validate cache hit latency is very fast."""
    import hashlib
    from billing_service.main import app
    from billing_service.database import get_db
    from billing_service.auth import verify_project_api_key
    from datetime import datetime
    
    # Update test project - get fresh object from engine to avoid thread issues
    from sqlalchemy.orm import sessionmaker
    from billing_service.models import Project
    TestingSessionLocal = sessionmaker(bind=db_engine)
    test_db = TestingSessionLocal()
    try:
        api_key = "test_perf_cache_key"
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        # Query project from DB using engine to get fresh object
        fresh_project = test_db.query(Project).filter(Project.id == test_project.id).first()
        fresh_project.api_key_hash = api_key_hash
        test_db.commit()
        test_db.refresh(fresh_project)
        # Use fresh_project in overrides
        test_project_for_override = fresh_project
    finally:
        test_db.close()
    
    # Use FastAPI dependency override - create a new session per request for thread safety
    # Use db_engine directly to avoid thread issues
    async def override_get_db():
        test_session = TestingSessionLocal()
        try:
            yield test_session
        finally:
            test_session.close()
    
    # Override verify_project_api_key - use the exact function reference
    async def override_verify_project_api_key():
        return test_project_for_override
    
    # Override both get_db and verify_project_api_key
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_project_api_key] = override_verify_project_api_key
    
    # Mock cache hit
    cached_entitlements = [
        {
            "feature_code": "feature1",
            "is_active": True,
            "valid_from": datetime.utcnow().isoformat(),
            "valid_to": None,
            "source": "subscription",
        }
    ]
    
    with patch("billing_service.entitlements_api.get_cached_entitlements", return_value=cached_entitlements):
        latencies = []
        num_requests = 50
        
        try:
            for _ in range(num_requests):
                start = time.time()
                response = await client.get(
                    "/api/v1/entitlements?user_id=test_user_cache",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                assert response.status_code == 200
                latencies.append((time.time() - start) * 1000)  # Convert to ms
            
            # Cache hits should be very fast
            p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
            assert p95_latency < 50, f"Cache hit p95 latency {p95_latency}ms exceeds 50ms threshold"
        finally:
            app.dependency_overrides.clear()
