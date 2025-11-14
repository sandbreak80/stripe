"""Scheduler for periodic reconciliation jobs."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from billing_service.reconciliation import reconcile_all

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def start_reconciliation_scheduler() -> None:
    """Start the reconciliation scheduler."""
    global _scheduler

    if _scheduler:
        logger.warning("Reconciliation scheduler already started")
        return

    _scheduler = BackgroundScheduler()
    # Run daily at 2 AM UTC
    _scheduler.add_job(
        reconcile_all,
        trigger=CronTrigger(hour=2, minute=0),
        id="daily_reconciliation",
        name="Daily Stripe Reconciliation",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Reconciliation scheduler started (daily at 2 AM UTC)")


def stop_reconciliation_scheduler() -> None:
    """Stop the reconciliation scheduler."""
    global _scheduler

    if _scheduler:
        _scheduler.shutdown()
        _scheduler = None
        logger.info("Reconciliation scheduler stopped")
