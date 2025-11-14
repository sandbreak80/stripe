"""Main FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from billing_service.admin import router as admin_router
from billing_service.checkout_api import router as checkout_router
from billing_service.entitlements_api import router as entitlements_router

# Register event processors
from billing_service.event_processors import (
    ChargeRefundedProcessor,
    CheckoutSessionCompletedProcessor,
    CustomerSubscriptionDeletedProcessor,
    CustomerSubscriptionUpdatedProcessor,
    InvoicePaymentSucceededProcessor,
)
from billing_service.metrics import router as metrics_router
from billing_service.portal_api import router as portal_router
from billing_service.prometheus_metrics import router as prometheus_router
from billing_service.scheduler import (
    start_reconciliation_scheduler,
    stop_reconciliation_scheduler,
)
from billing_service.schemas import HealthResponse
from billing_service.webhook_processors import event_router
from billing_service.webhooks import router as webhooks_router

# Register processors
event_router.register_processor(CheckoutSessionCompletedProcessor())
event_router.register_processor(InvoicePaymentSucceededProcessor())
event_router.register_processor(CustomerSubscriptionUpdatedProcessor())
event_router.register_processor(CustomerSubscriptionDeletedProcessor())
event_router.register_processor(ChargeRefundedProcessor())

app = FastAPI(
    title="Billing Service",
    description="Centralized Billing & Entitlements Service",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(checkout_router)
app.include_router(entitlements_router)
app.include_router(portal_router)
app.include_router(webhooks_router)
app.include_router(admin_router)
app.include_router(metrics_router)
app.include_router(prometheus_router)


@app.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy")


@app.get("/ready", response_model=HealthResponse)
async def readiness_check() -> HealthResponse | JSONResponse:
    """Readiness check endpoint."""
    from billing_service.database import check_db_connection

    if not check_db_connection():
        from fastapi import status

        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready"},
        )

    return HealthResponse(status="ready")


@app.get("/live", response_model=HealthResponse)
async def liveness_check() -> HealthResponse:
    """Liveness check endpoint."""
    return HealthResponse(status="alive")


# Start reconciliation scheduler on startup
@app.on_event("startup")
async def startup_event() -> None:
    """Start background tasks on application startup."""
    start_reconciliation_scheduler()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Cleanup on application shutdown."""
    stop_reconciliation_scheduler()
