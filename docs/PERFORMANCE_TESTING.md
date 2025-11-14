# Performance Testing Guide

**Version:** 1.0  
**Last Updated:** November 11, 2025  
**Service:** Centralized Billing & Entitlements Service

## Overview

This guide describes procedures for validating performance targets and conducting load testing for the Billing Service. The primary performance target is **<100ms p95 latency** for entitlement checks.

## Performance Targets

### Entitlement Check SLA
- **Target**: <100ms p95 latency for `GET /api/v1/entitlements` endpoint
- **Measurement**: Response time from request received to response sent
- **Conditions**: Under normal load (100 requests/second)

### Other Performance Targets
- **Checkout Session Creation**: <500ms p95 latency
- **Webhook Processing**: <1s p95 latency (async processing)
- **Database Queries**: <50ms p95 latency
- **Cache Hit Rate**: >80% for entitlement queries

## Prerequisites

### Required Tools
- **Load Testing Tool**: Locust, k6, or Apache Bench (ab)
- **Monitoring**: Prometheus + Grafana (or equivalent)
- **Database**: PostgreSQL with connection pooling enabled
- **Cache**: Redis with sufficient memory

### Test Environment Setup

1. **Start services with monitoring**:
```bash
docker compose up -d
docker compose exec app alembic upgrade head
```

2. **Verify services are healthy**:
```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/ready
```

3. **Set up test data**:
   - Create test projects via database
   - Create test subscriptions/purchases
   - Pre-populate Redis cache (optional)

## Load Testing Procedures

### 1. Entitlement Check Load Test

**Objective**: Validate <100ms p95 latency for entitlement checks under load.

**Using Locust**:

Create `locustfile.py`:
```python
from locust import HttpUser, task, between
import random

class EntitlementCheckUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # Set up authentication
        self.api_key = "your_test_api_key"
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        self.user_ids = [f"user_{i}" for i in range(1000)]
        self.project_id = "test-project"
    
    @task(10)
    def check_entitlements(self):
        user_id = random.choice(self.user_ids)
        self.client.get(
            f"/api/v1/entitlements?user_id={user_id}&project_id={self.project_id}",
            headers=self.headers,
            name="check_entitlements"
        )
```

**Run test**:
```bash
# Install Locust
pip install locust

# Start Locust web UI
locust -f locustfile.py --host=http://localhost:8000

# Or run headless
locust -f locustfile.py --host=http://localhost:8000 --headless -u 100 -r 10 -t 5m
```

**Parameters**:
- `-u 100`: 100 concurrent users
- `-r 10`: Spawn rate of 10 users/second
- `-t 5m`: Run for 5 minutes

**Using k6**:

Create `entitlement_check_test.js`:
```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 50 },
    { duration: '1m', target: 100 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<100'], // p95 < 100ms
  },
};

const API_KEY = 'your_test_api_key';
const BASE_URL = 'http://localhost:8000';

export default function () {
  const user_id = `user_${Math.floor(Math.random() * 1000)}`;
  const project_id = 'test-project';
  
  const params = {
    headers: {
      'Authorization': `Bearer ${API_KEY}`,
    },
  };
  
  const res = http.get(
    `${BASE_URL}/api/v1/entitlements?user_id=${user_id}&project_id=${project_id}`,
    params
  );
  
  check(res, {
    'status is 200': (r) => r.status === 200,
    'p95 < 100ms': (r) => r.timings.duration < 100,
  });
  
  sleep(1);
}
```

**Run test**:
```bash
k6 run entitlement_check_test.js
```

### 2. Checkout Session Creation Load Test

**Objective**: Validate <500ms p95 latency for checkout session creation.

**Test Script** (Locust):
```python
@task(5)
def create_checkout(self):
    user_id = random.choice(self.user_ids)
    payload = {
        "user_id": user_id,
        "project_id": self.project_id,
        "price_id": "test-price-id",
        "mode": "subscription",
        "success_url": "https://example.com/success",
        "cancel_url": "https://example.com/cancel",
    }
    self.client.post(
        "/api/v1/checkout/create",
        json=payload,
        headers=self.headers,
        name="create_checkout"
    )
```

### 3. Webhook Processing Load Test

**Objective**: Validate webhook processing can handle Stripe's rate limits.

**Note**: Webhooks are processed asynchronously, so response time should be <1s.

**Test Script**:
```python
@task(2)
def process_webhook(self):
    # Simulate Stripe webhook payload
    payload = {
        "id": f"evt_{random.randint(1000, 9999)}",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": f"cs_test_{random.randint(1000, 9999)}",
                "mode": "subscription",
                "metadata": {
                    "user_id": random.choice(self.user_ids),
                    "project_id": self.project_id,
                },
            }
        }
    }
    self.client.post(
        "/api/v1/webhooks/stripe",
        json=payload,
        headers={"Stripe-Signature": "test_signature"},
        name="process_webhook"
    )
```

## Monitoring During Tests

### Prometheus Metrics

The service exposes metrics at `/metrics` endpoint. Key metrics to monitor:

- `http_request_duration_seconds` - Request latency histogram
- `http_requests_total` - Total request count
- `entitlement_cache_hits_total` - Cache hit count
- `entitlement_cache_misses_total` - Cache miss count
- `database_query_duration_seconds` - Database query latency

### Database Monitoring

Monitor PostgreSQL:
- Connection pool usage
- Query execution time
- Lock contention
- Cache hit ratio

### Redis Monitoring

Monitor Redis:
- Memory usage
- Hit/miss ratio
- Connection count
- Command latency

## Performance Baseline

### Expected Results (Single Instance)

**Entitlement Checks** (with Redis cache):
- **p50**: <20ms
- **p95**: <50ms
- **p99**: <100ms
- **Cache Hit Rate**: >80%

**Without Cache**:
- **p50**: <50ms
- **p95**: <150ms
- **p99**: <300ms

### Scaling Considerations

- **Horizontal Scaling**: Stateless API allows horizontal scaling
- **Database**: Consider read replicas for high read load
- **Cache**: Redis cluster for high availability
- **Connection Pooling**: Tune PostgreSQL connection pool size

## Troubleshooting Performance Issues

### High Latency on Entitlement Checks

1. **Check cache hit rate**: Low hit rate indicates cache invalidation issues
2. **Check database queries**: Slow queries may need indexing
3. **Check Redis latency**: Network issues or Redis overload
4. **Check connection pool**: Exhausted pool causes queuing

### High Latency on Checkout Creation

1. **Check Stripe API latency**: External dependency
2. **Check database writes**: Slow inserts may need optimization
3. **Check connection pool**: Database connection exhaustion

### Webhook Processing Delays

1. **Check event processor queue**: Backlog indicates processing bottleneck
2. **Check database locks**: Concurrent updates may cause contention
3. **Check Stripe API calls**: External API latency

## Performance Regression Testing

### Automated Performance Tests

Add performance tests to CI/CD pipeline:

```python
# tests/test_performance.py
import pytest
import time
from statistics import median

@pytest.mark.performance
def test_entitlement_check_p95_latency(client, test_project):
    """Validate p95 latency < 100ms."""
    latencies = []
    for _ in range(100):
        start = time.time()
        response = client.get(
            f"/api/v1/entitlements?user_id=test_user&project_id={test_project.project_id}",
            headers={"Authorization": f"Bearer {test_project.api_key}"}
        )
        assert response.status_code == 200
        latencies.append((time.time() - start) * 1000)  # Convert to ms
    
    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95)]
    assert p95 < 100, f"p95 latency {p95}ms exceeds 100ms threshold"
```

**Run performance tests**:
```bash
pytest tests/test_performance.py -m performance
```

## Continuous Performance Monitoring

### Production Monitoring

1. **Set up alerts** for p95 latency > 100ms
2. **Monitor cache hit rate** - alert if <70%
3. **Monitor database query times** - alert if p95 > 50ms
4. **Monitor error rates** - alert if >1%

### Performance Dashboards

Create Grafana dashboards for:
- Request latency (p50, p95, p99)
- Cache hit/miss rates
- Database query performance
- Error rates by endpoint
- Throughput (requests/second)

## Best Practices

1. **Run load tests regularly** (weekly/monthly)
2. **Test before major releases** to catch regressions
3. **Monitor production metrics** continuously
4. **Set up alerts** for performance degradation
5. **Document performance characteristics** of each release
6. **Test with realistic data** volumes and patterns

## References

- [Locust Documentation](https://docs.locust.io/)
- [k6 Documentation](https://k6.io/docs/)
- [Prometheus Monitoring](https://prometheus.io/docs/)
- [PostgreSQL Performance Tuning](https://www.postgresql.org/docs/current/performance-tips.html)
