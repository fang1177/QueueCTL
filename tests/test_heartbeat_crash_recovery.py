"""
QueueCTL Worker Heartbeat & Crash Recovery Tests.

Validates heartbeat status updates, stale worker identification, and automatic
reclaiming of processing jobs stuck under crashed workers.
"""

from datetime import datetime, timedelta, timezone
import pytest
from queuectl.models.enums import JobState, WorkerStatus
from queuectl.models.job import JobCreate
from queuectl.repositories.job_repository import JobRepository
from queuectl.repositories.worker_repository import WorkerRepository
from queuectl.services.recovery_service import CrashRecoveryService
from queuectl.utils.time_utils import utc_now


def test_worker_heartbeat_update(db_manager):
    """Tests worker registration and heartbeat updates."""
    with db_manager.session() as session:
        repo = WorkerRepository(session)
        worker = repo.register("worker-test-1", pid=1234, hostname="localhost")
        assert worker.status == WorkerStatus.ACTIVE.value

        updated = repo.update_heartbeat("worker-test-1", current_job_id="job-999")
        assert updated.current_job_id == "job-999"


def test_crash_recovery_engine(db_manager, queue_service):
    """
    Simulates a SIGKILL worker crash:
    1. Worker claims a job and moves state to 'processing'.
    2. Worker process terminates instantly without updating heartbeat.
    3. Crash recovery engine runs, detects heartbeat timeout (>30s), marks worker DEAD,
       and automatically resets job back to 'pending' for another worker to execute.
    """
    worker_id = "dead-worker-99"

    # Step 1: Register worker and claim a job
    job_dict = queue_service.enqueue(JobCreate(name="Crash Test Job", command="sleep 10"))
    job_id = job_dict["id"]

    with db_manager.session() as session:
        w_repo = WorkerRepository(session)
        j_repo = JobRepository(session)

        worker = w_repo.register(worker_id, pid=9999, hostname="crash-host")
        
        # Simulate stale last_heartbeat timestamp from 40 seconds ago (exceeding 30s timeout)
        stale_time = utc_now() - timedelta(seconds=40)
        worker.last_heartbeat = stale_time

        # Claim job for worker
        job = j_repo.get_by_id(job_id)
        job.state = JobState.PROCESSING.value
        job.worker_id = worker_id
        job.started_at = stale_time

    # Step 2: Run crash recovery check
    recovery_service = CrashRecoveryService(db_manager)
    result = recovery_service.recover_stale_workers_and_jobs()

    # Step 3: Assert crash recovery success
    assert worker_id in result["dead_workers_recovered"]
    assert job_id in result["reclaimed_jobs"]

    reclaimed_job = queue_service.get_job(job_id)
    assert reclaimed_job["state"] == JobState.PENDING.value
    assert reclaimed_job["worker_id"] is None
    assert reclaimed_job["attempts"] == 1
    assert "Reclaimed after worker" in reclaimed_job["error_message"]
