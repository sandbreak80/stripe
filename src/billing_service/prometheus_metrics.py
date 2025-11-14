"""Prometheus metrics endpoint for operational monitoring."""

from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

router = APIRouter(prefix="/metrics", tags=["metrics"])

# HTTP request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

# Database metrics
db_connections_active = Gauge(
    "db_connections_active",
    "Number of active database connections"
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"]
)

# Redis metrics
redis_operations_total = Counter(
    "redis_operations_total",
    "Total number of Redis operations",
    ["operation", "status"]
)

redis_operation_duration_seconds = Histogram(
    "redis_operation_duration_seconds",
    "Redis operation duration in seconds",
    ["operation"]
)

# Business metrics
active_subscriptions_total = Gauge(
    "active_subscriptions_total",
    "Total number of active subscriptions",
    ["project_id", "status"]
)

entitlements_cache_hits_total = Counter(
    "entitlements_cache_hits_total",
    "Total number of entitlements cache hits"
)

entitlements_cache_misses_total = Counter(
    "entitlements_cache_misses_total",
    "Total number of entitlements cache misses"
)

webhook_events_processed_total = Counter(
    "webhook_events_processed_total",
    "Total number of webhook events processed",
    ["event_type", "status"]
)

reconciliation_runs_total = Counter(
    "reconciliation_runs_total",
    "Total number of reconciliation runs",
    ["status"]
)

reconciliation_duration_seconds = Histogram(
    "reconciliation_duration_seconds",
    "Reconciliation job duration in seconds"
)


@router.get("")
async def get_metrics() -> Response:
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
