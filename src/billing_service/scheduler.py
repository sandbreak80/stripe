"""Scheduled job system for reconciliation."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from billing_service.config import settings
from billing_service.database import get_db
from billing_service.reconciliation import reconcile_all

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: BackgroundScheduler | None = None


def run_reconciliation_job() -> None:
    """Execute reconciliation job."""
    try:
        logger.info("Starting scheduled reconciliation job")
        db = next(get_db())
        try:
            result = reconcile_all(db, days_back=settings.reconciliation_days_back)
            logger.info(
                f"Reconciliation completed: {result['subscriptions']['subscriptions_checked']} "
                f"subscriptions checked, {result['purchases']['purchases_checked']} purchases checked"
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error during scheduled reconciliation: {e}", exc_info=True)


def start_scheduler() -> None:
    """Start the background scheduler."""
    global scheduler

    if scheduler is not None:
        logger.warning("Scheduler already started")
        return

    if not settings.reconciliation_enabled:
        logger.info("Reconciliation scheduling is disabled")
        return

    scheduler = BackgroundScheduler()
    scheduler.start()

    # Schedule daily reconciliation at configured hour
    scheduler.add_job(
        func=run_reconciliation_job,
        trigger=CronTrigger(hour=settings.reconciliation_schedule_hour, minute=0),
        id="reconciliation_job",
        name="Daily Reconciliation",
        replace_existing=True,
    )

    logger.info(
        f"Scheduler started: Reconciliation scheduled daily at {settings.reconciliation_schedule_hour}:00 UTC"
    )


def stop_scheduler() -> None:
    """Stop the background scheduler."""
    global scheduler

    if scheduler is None:
        return

    scheduler.shutdown()
    scheduler = None
    logger.info("Scheduler stopped")
