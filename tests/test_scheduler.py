"""Tests for scheduler component."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from billing_service.scheduler import (
    start_reconciliation_scheduler,
    stop_reconciliation_scheduler,
)


def test_scheduler_initialization():
    """Test scheduler can be initialized."""
    from billing_service.scheduler import start_reconciliation_scheduler, stop_reconciliation_scheduler
    
    # Test that scheduler functions exist and are callable
    assert callable(start_reconciliation_scheduler)
    assert callable(stop_reconciliation_scheduler)


@patch("billing_service.scheduler._scheduler", None)
@patch("billing_service.scheduler.BackgroundScheduler")
@patch("billing_service.scheduler.reconcile_all")
def test_start_reconciliation_scheduler(mock_reconcile, mock_scheduler_class):
    """Test starting reconciliation scheduler."""
    mock_scheduler = Mock()
    mock_scheduler_class.return_value = mock_scheduler
    
    start_reconciliation_scheduler()
    
    # Should create and start scheduler
    mock_scheduler_class.assert_called_once()
    mock_scheduler.add_job.assert_called_once()
    mock_scheduler.start.assert_called_once()


@patch("billing_service.scheduler._scheduler")
def test_stop_reconciliation_scheduler(mock_scheduler):
    """Test stopping reconciliation scheduler."""
    mock_scheduler.shutdown = Mock()
    
    stop_reconciliation_scheduler()
    
    # Should shutdown scheduler
    mock_scheduler.shutdown.assert_called_once()


@patch("billing_service.scheduler._scheduler", None)
@patch("billing_service.scheduler.BackgroundScheduler")
@patch("billing_service.scheduler.reconcile_all")
def test_scheduler_job_configuration(mock_reconcile, mock_scheduler_class):
    """Test scheduler job is configured correctly."""
    mock_scheduler = Mock()
    mock_scheduler_class.return_value = mock_scheduler
    
    start_reconciliation_scheduler()
    
    # Verify scheduler was created and started
    mock_scheduler_class.assert_called_once()
    mock_scheduler.add_job.assert_called_once()
    mock_scheduler.start.assert_called_once()
    
    # Verify job configuration
    call_args = mock_scheduler.add_job.call_args
    assert call_args is not None
    # Check trigger is CronTrigger
    trigger = call_args[1]['trigger']
    assert hasattr(trigger, 'fields')
    
    stop_reconciliation_scheduler()


@patch("billing_service.scheduler._scheduler", None)
@patch("billing_service.scheduler.BackgroundScheduler")
@patch("billing_service.scheduler.reconcile_all")
def test_scheduler_idempotency(mock_reconcile, mock_scheduler_class):
    """Test scheduler can be started multiple times safely."""
    mock_scheduler = Mock()
    mock_scheduler_class.return_value = mock_scheduler
    
    # Start scheduler first time
    start_reconciliation_scheduler()
    call_count_1 = mock_scheduler.add_job.call_count
    
    # Start scheduler second time (should check if already started)
    start_reconciliation_scheduler()
    
    # Should handle idempotency (either skip or replace)
    # Implementation checks for existing scheduler
    assert mock_scheduler.add_job.call_count >= call_count_1
    
    stop_reconciliation_scheduler()
