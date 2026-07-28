"""
QueueCTL Enqueue Unit Tests.

Tests job creation, default parameter application, priority sorting, and delayed jobs.
"""

from datetime import datetime, timezone
import pytest
from queuectl.models.job import JobCreate
from queuectl.models.enums import JobState


def test_enqueue_basic_job(queue_service):
    """Tests enqueueing a standard job with default settings."""
    payload = JobCreate(name="Test Job 1", command="echo 'hello'")
    job_dict = queue_service.enqueue(payload)

    assert job_dict["id"] is not None
    assert job_dict["name"] == "Test Job 1"
    assert job_dict["command"] == "echo 'hello'"
    assert job_dict["state"] == JobState.PENDING.value
    assert job_dict["priority"] == 0
    assert job_dict["attempts"] == 0
    assert job_dict["max_retries"] == 3
    assert job_dict["backoff_base"] == 2.0


def test_enqueue_custom_parameters(queue_service):
    """Tests enqueueing job with explicit priority, retries, and timeout."""
    payload = JobCreate(
        name="Custom Job",
        command="python -c 'print(42)'",
        priority=10,
        max_retries=5,
        backoff_base=3.0,
        timeout=120,
    )
    job_dict = queue_service.enqueue(payload)

    assert job_dict["priority"] == 10
    assert job_dict["max_retries"] == 5
    assert job_dict["backoff_base"] == 3.0
    assert job_dict["timeout"] == 120


def test_enqueue_delayed_job(queue_service):
    """Tests enqueueing a delayed job with scheduled_at setting."""
    payload = JobCreate(
        name="Delayed Job",
        command="echo 'delayed'",
        delay_seconds=30,
    )
    job_dict = queue_service.enqueue(payload)

    assert job_dict["scheduled_at"] is not None
    scheduled_dt = datetime.fromisoformat(job_dict["scheduled_at"])
    assert scheduled_dt > datetime.now(timezone.utc)
