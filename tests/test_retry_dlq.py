"""
QueueCTL Exponential Backoff & DLQ Unit Tests.

Tests retry attempt increments, exponential backoff scheduling, transition to DEAD state,
and manual DLQ job reset.
"""

from datetime import datetime, timezone
import pytest
from queuectl.core.backoff import calculate_backoff_delay
from queuectl.models.enums import JobState
from queuectl.models.job import JobCreate
from queuectl.repositories.job_repository import JobRepository


def test_exponential_backoff_calculator():
    """Validates calculate_backoff_delay formula (base ^ attempt)."""
    assert calculate_backoff_delay(0, 2.0) == 0.0
    assert calculate_backoff_delay(1, 2.0) == 2.0
    assert calculate_backoff_delay(2, 2.0) == 4.0
    assert calculate_backoff_delay(3, 2.0) == 8.0
    assert calculate_backoff_delay(4, 2.0) == 16.0
    
    # Custom base 3.0
    assert calculate_backoff_delay(2, 3.0) == 9.0


def test_retry_and_dlq_transition(db_manager, queue_service):
    """Tests job failure retries up to max_retries and subsequent DLQ transition."""
    job_dict = queue_service.enqueue(JobCreate(
        name="Failing Job",
        command="exit 1",
        max_retries=2,
        backoff_base=2.0
    ))
    job_id = job_dict["id"]

    with db_manager.session() as session:
        repo = JobRepository(session)

        # Attempt 1: Failed
        j1 = repo.mark_failed(job_id, error_message="Exit status 1")
        assert j1.attempts == 1
        assert j1.state == JobState.PENDING.value
        assert j1.scheduled_at is not None
        assert j1.scheduled_at > datetime.now(timezone.utc)

        # Attempt 2: Failed (Reaches max_retries = 2)
        j2 = repo.mark_failed(job_id, error_message="Exit status 1 second time")
        assert j2.attempts == 2
        assert j2.state == JobState.DEAD.value  # Moved to DLQ!
        assert j2.worker_id is None


def test_dlq_manual_retry(db_manager, queue_service):
    """Tests resetting a DLQ (dead) job back to pending state."""
    job_dict = queue_service.enqueue(JobCreate(
        name="Dead Job",
        command="exit 1",
        max_retries=1
    ))
    job_id = job_dict["id"]

    with db_manager.session() as session:
        repo = JobRepository(session)
        repo.mark_failed(job_id, error_message="Fatal error")

    # Verify dead state
    j_dead = queue_service.get_job(job_id)
    assert j_dead["state"] == JobState.DEAD.value

    # Reset DLQ job
    retried_dict = queue_service.retry_dlq_job(job_id)
    assert retried_dict["state"] == JobState.PENDING.value
    assert retried_dict["attempts"] == 0
    assert retried_dict["error_message"] is None
