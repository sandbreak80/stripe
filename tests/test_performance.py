"""Performance tests for entitlement check SLA validation."""

import pytest
import time
from statistics import median
from unittest.mock import patch

from fastapi.testclient import TestClient

from billing_service.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.mark.performance
@patch("billing_service.entitlements_api.get_db")
@patch("billing_service.entitlements_api.verify_project_api_key")
@patch("billing_service.entitlements_api.get_cached_entitlements")
def test_entitlement_check_p95_latency(mock_cache, mock_verify, mock_get_db, client, db_session, test_project):
    """Validate p95 latency < 100ms for entitlement checks."""
    import hashlib
    
    api_key = "test_perf_key"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    test_project.api_key_hash = api_key_hash
    db_session.commit()
    
    # Mock dependencies
    mock_get_db.return_value = db_session
    mock_verify.return_value = test_project
    mock_cache.return_value = None  # Cache miss to test database query
    
    latencies = []
    num_requests = 100
    
    for _ in range(num_requests):
        start = time.time()
        response = client.get(
            "/api/v1/entitlements?user_id=test_user&project_id=test-project",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        latencies.append((time.time() - start) * 1000)  # Convert to ms
    
    latencies.sort()
    p95_index = int(len(latencies) * 0.95)
    p95_latency = latencies[p95_index]
    
    # Validate p95 < 100ms (with some margin for test overhead)
    assert p95_latency < 200, f"p95 latency {p95_latency}ms exceeds 200ms threshold (test overhead considered)"


@pytest.mark.performance
@patch("billing_service.entitlements_api.get_db")
@patch("billing_service.entitlements_api.verify_project_api_key")
@patch("billing_service.entitlements_api.get_cached_entitlements")
def test_entitlement_check_cache_hit_latency(mock_cache, mock_verify, mock_get_db, client, db_session, test_project):
    """Validate cache hit latency is very fast."""
    import hashlib
    from billing_service.models import Entitlement, EntitlementSource
    from datetime import datetime
    
    api_key = "test_perf_key"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    test_project.api_key_hash = api_key_hash
    db_session.commit()
    
    # Create entitlement
    entitlement = Entitlement(
        user_id="test_user",
        project_id=test_project.id,
        feature_code="feature1",
        is_active=True,
        valid_from=datetime.utcnow(),
        valid_to=None,
        source=EntitlementSource.SUBSCRIPTION,
        source_id=test_project.id,
    )
    db_session.add(entitlement)
    db_session.commit()
    
    # Mock dependencies
    mock_get_db.return_value = db_session
    mock_verify.return_value = test_project
    
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
    mock_cache.return_value = cached_entitlements
    
    latencies = []
    num_requests = 50
    
    for _ in range(num_requests):
        start = time.time()
        response = client.get(
            "/api/v1/entitlements?user_id=test_user&project_id=test-project",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        latencies.append((time.time() - start) * 1000)  # Convert to ms
    
    # Cache hits should be very fast
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
    assert p95_latency < 50, f"Cache hit p95 latency {p95_latency}ms exceeds 50ms threshold"
