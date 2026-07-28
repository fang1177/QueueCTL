"""
QueueCTL Atomic Job Claiming & Concurrency Integration Tests.

Validates that concurrent worker processes claiming jobs simultaneously from SQLite
never claim the same job twice (Exactly-Once Job Claiming).
"""

from concurrent.futures import ProcessPoolExecutor, as_completed
import os
import pytest
from queuectl.database.connection import get_db_manager
from queuectl.models.job import JobCreate
from queuectl.repositories.job_repository import JobRepository
from queuectl.services.queue_service import QueueService


def _claim_jobs_worker(db_path: str, worker_id: str, claim_count: int):
    """Worker process task: continuously claim jobs atomically."""
    db_manager = get_db_manager(db_path)
    claimed_ids = []

    for _ in range(claim_count):
        with db_manager.session() as session:
            repo = JobRepository(session)
            job = repo.claim_next_job(worker_id)
            if job:
                claimed_ids.append(job.id)

    return claimed_ids


def test_concurrent_atomic_job_claiming(temp_db_path):
    """
    Spawns 5 parallel processes attempting to claim 50 jobs concurrently.
    Verifies that zero duplicate job claims occur across all workers.
    """
    db_manager = get_db_manager(temp_db_path)
    queue_service = QueueService(db_manager)

    # Step 1: Enqueue 50 pending jobs
    total_jobs = 50
    for i in range(total_jobs):
        queue_service.enqueue(JobCreate(name=f"Job {i}", command="echo 1"))

    num_workers = 5
    claims_per_worker = 15

    all_claimed_ids = []

    # Step 2: Launch 5 parallel processes concurrently claiming jobs
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = [
            executor.submit(_claim_jobs_worker, temp_db_path, f"worker-{i}", claims_per_worker)
            for i in range(num_workers)
        ]

        for future in as_completed(futures):
            res = future.result()
            all_claimed_ids.extend(res)

    # Step 3: Assert Exactly-Once semantics
    assert len(all_claimed_ids) == total_jobs, f"Expected {total_jobs} total claimed jobs, got {len(all_claimed_ids)}"
    assert len(set(all_claimed_ids)) == total_jobs, "CRITICAL: Duplicate job claims detected across concurrent processes!"
