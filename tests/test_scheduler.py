"""Tests for scheduler module."""

from unittest.mock import MagicMock, patch

import pytest

from billing_service.scheduler import run_reconciliation_job, start_scheduler, stop_scheduler


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.__enter__ = MagicMock(return_value=db)
    db.__exit__ = MagicMock(return_value=None)
    return db


@patch("billing_service.scheduler.get_db")
@patch("billing_service.scheduler.reconcile_all")
def test_run_reconciliation_job_success(mock_reconcile, mock_get_db, mock_db):
    """Test successful reconciliation job execution."""
    mock_get_db.return_value = iter([mock_db])
    mock_reconcile.return_value = {
        "reconciliation_date": "2024-01-01T00:00:00",
        "days_back": 7,
        "subscriptions": {"subscriptions_checked": 10, "drift_detected": 2, "corrected": 2},
        "purchases": {"purchases_checked": 5, "drift_detected": 1, "corrected": 1},
    }

    run_reconciliation_job()

    mock_reconcile.assert_called_once_with(mock_db, days_back=7)
    mock_db.close.assert_called_once()


@patch("billing_service.scheduler.get_db")
@patch("billing_service.scheduler.reconcile_all")
def test_run_reconciliation_job_error(mock_reconcile, mock_get_db, mock_db):
    """Test reconciliation job handles errors gracefully."""
    mock_get_db.return_value = iter([mock_db])
    mock_reconcile.side_effect = Exception("Test error")

    # Should not raise
    run_reconciliation_job()

    mock_db.close.assert_called_once()


@patch("billing_service.scheduler.BackgroundScheduler")
@patch("billing_service.scheduler.settings")
def test_start_scheduler_enabled(mock_settings, mock_scheduler_class):
    """Test scheduler starts when enabled."""
    mock_settings.reconciliation_enabled = True
    mock_settings.reconciliation_schedule_hour = 2
    mock_settings.reconciliation_days_back = 7
    mock_scheduler = MagicMock()
    mock_scheduler_class.return_value = mock_scheduler

    # Reset global scheduler
    import billing_service.scheduler

    billing_service.scheduler.scheduler = None

    start_scheduler()

    mock_scheduler_class.assert_called_once()
    mock_scheduler.start.assert_called_once()
    assert mock_scheduler.add_job.call_count == 1


@patch("billing_service.scheduler.BackgroundScheduler")
@patch("billing_service.scheduler.settings")
def test_start_scheduler_disabled(mock_settings, mock_scheduler_class):
    """Test scheduler does not start when disabled."""
    mock_settings.reconciliation_enabled = False

    # Reset global scheduler
    import billing_service.scheduler

    billing_service.scheduler.scheduler = None

    start_scheduler()

    mock_scheduler_class.assert_not_called()


@patch("billing_service.scheduler.scheduler")
def test_stop_scheduler(mock_scheduler):
    """Test scheduler stops correctly."""
    import billing_service.scheduler

    billing_service.scheduler.scheduler = mock_scheduler

    stop_scheduler()

    mock_scheduler.shutdown.assert_called_once()
    assert billing_service.scheduler.scheduler is None


@patch("billing_service.scheduler.scheduler")
def test_stop_scheduler_none(mock_scheduler):
    """Test stopping scheduler when None."""
    import billing_service.scheduler

    billing_service.scheduler.scheduler = None

    stop_scheduler()

    mock_scheduler.shutdown.assert_not_called()
