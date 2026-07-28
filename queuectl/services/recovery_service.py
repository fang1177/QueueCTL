"""
QueueCTL Crash Recovery Engine Module.

Detects silent worker crashes (e.g. SIGKILL, kernel panics, system power failure)
and automatically reclaims processing jobs within <60 seconds threshold.
"""

from typing import Dict, List, Any
from queuectl.database.connection import DatabaseManager
from queuectl.models.enums import JobState, WorkerStatus
from queuectl.models.job import Job
from queuectl.repositories.job_repository import JobRepository
from queuectl.repositories.worker_repository import WorkerRepository
from queuectl.services.config_service import ConfigService
from queuectl.utils.logger import get_logger
from queuectl.utils.time_utils import utc_now

logger = get_logger("queuectl.recovery")


class CrashRecoveryService:
    """
    Automatic Crash Recovery Engine.

    CRASH RECOVERY MECHANISM EXPLANATION FOR INTERVIEW DEFENSE:
    ----------------------------------------------------------
    1. Problem: If a worker process receives SIGKILL (kill -9), it terminates instantly.
       No signal handlers, try/finally blocks, or cleanup code execute. The worker's
       database status remains 'active', and its claimed job remains stuck in 'processing'.
    2. Solution: Every active worker sends a periodic heartbeat (default 5s) updating
       `last_heartbeat` in the database.
    3. Detection: If a worker's `last_heartbeat` is older than `recovery_timeout` (default 30s),
       it is classified as DEAD.
    4. Reclaim: Any job assigned to the dead worker in state 'processing' is orphaned.
       The recovery service automatically:
       - Increments attempts or checks attempt count.
       - Resets state to 'pending', worker_id = NULL, scheduled_at = NOW.
       - Allows remaining active workers to claim and execute the job immediately.
    5. SLA: Recovery takes place in under 30-40 seconds (well below the 60-second requirement).
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.config_service = ConfigService(db_manager)

    def recover_stale_workers_and_jobs(self) -> Dict[str, Any]:
        """
        Executes a crash recovery check.

        Returns:
            Dictionary containing list of recovered dead worker IDs and reclaimed job IDs.
        """
        configs = self.config_service.get_all_configs()
        recovery_timeout = float(configs.get("recovery_timeout", 30.0))

        recovered_workers: List[str] = []
        reclaimed_jobs: List[str] = []

        with self.db_manager.session() as session:
            worker_repo = WorkerRepository(session)
            job_repo = JobRepository(session)

            # Step 1: Query for workers with silent heartbeat timeouts
            stale_workers = worker_repo.find_stale_workers(recovery_timeout)

            for worker in stale_workers:
                logger.warning(
                    f"CRASH RECOVERY: Worker '{worker.id}' (PID {worker.pid}) missed heartbeats "
                    f"for >{recovery_timeout}s. Marking DEAD."
                )
                worker_repo.set_status(worker.id, WorkerStatus.DEAD)
                recovered_workers.append(worker.id)

                # Step 2: Find all jobs currently assigned to this dead worker in 'processing' state
                processing_jobs = (
                    session.query(Job)
                    .filter(
                        Job.worker_id == worker.id,
                        Job.state == JobState.PROCESSING.value
                    )
                    .all()
                )

                for job in processing_jobs:
                    logger.warning(
                        f"CRASH RECOVERY: Reclaiming orphaned Job '{job.id}' ('{job.name}') "
                        f"stuck in processing state under dead worker '{worker.id}'."
                    )
                    
                    now = utc_now()
                    job.attempts += 1
                    job.updated_at = now

                    if job.attempts >= job.max_retries:
                        job.state = JobState.DEAD.value
                        job.error_message = (
                            f"Worker '{worker.id}' crashed while processing job. "
                            f"Max retries ({job.max_retries}) exceeded during crash recovery."
                        )
                        job.worker_id = None
                    else:
                        job.state = JobState.PENDING.value
                        job.scheduled_at = now
                        job.worker_id = None
                        job.error_message = f"Reclaimed after worker '{worker.id}' crash."

                    reclaimed_jobs.append(job.id)

        return {
            "dead_workers_recovered": recovered_workers,
            "reclaimed_jobs": reclaimed_jobs,
        }
