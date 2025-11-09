"""Main FastAPI application entry point."""

import logging

from fastapi import FastAPI
from sqlalchemy import text

from billing_service.admin import router as admin_router
from billing_service.database import get_db
from billing_service.entitlements_api import router as entitlements_router
from billing_service.metrics import router as metrics_router
from billing_service.payments import router as payments_router
from billing_service.scheduler import start_scheduler, stop_scheduler
from billing_service.webhooks import router as webhooks_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Billing Service",
    description="Centralized Billing & Entitlements Service for Micro-Applications",
    version="0.1.0",
)

app.include_router(payments_router)
app.include_router(webhooks_router)
app.include_router(entitlements_router)
app.include_router(admin_router)
app.include_router(metrics_router)


@app.on_event("startup")
async def startup_event() -> None:
    """Startup event handler."""
    logger.info("Starting Billing Service...")
    start_scheduler()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Shutdown event handler."""
    logger.info("Shutting down Billing Service...")
    stop_scheduler()


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    """Readiness check endpoint - verifies database connectivity."""
    try:
        db = next(get_db())
        # Verify database connectivity
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "ready"}
    except Exception:
        return {"status": "not_ready"}


@app.get("/live")
async def live() -> dict[str, str]:
    """Liveness check endpoint."""
    return {"status": "alive"}
