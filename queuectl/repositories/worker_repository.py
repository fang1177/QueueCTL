"""
QueueCTL Worker Repository Module.

Manages worker registration, heartbeat tracking, status updates,
and stale worker detection.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from queuectl.models.enums import WorkerStatus
from queuectl.models.worker import Worker
from queuectl.utils.time_utils import utc_now


class WorkerRepository:
    """Data repository for worker processes and heartbeat registry."""

    def __init__(self, session: Session):
        self.session = session

    def register(self, worker_id: str, pid: int, hostname: str) -> Worker:
        """Registers or updates a worker process in the database."""
        now = utc_now()
        worker = self.session.get(Worker, worker_id)
        if not worker:
            worker = Worker(
                id=worker_id,
                pid=pid,
                hostname=hostname,
                status=WorkerStatus.ACTIVE.value,
                started_at=now,
                last_heartbeat=now,
                jobs_processed=0,
                jobs_failed=0,
            )
            self.session.add(worker)
        else:
            worker.pid = pid
            worker.hostname = hostname
            worker.status = WorkerStatus.ACTIVE.value
            worker.last_heartbeat = now

        self.session.flush()
        return worker

    def update_heartbeat(
        self,
        worker_id: str,
        current_job_id: Optional[str] = None
    ) -> Optional[Worker]:
        """Updates last_heartbeat timestamp and current job assignment."""
        worker = self.session.get(Worker, worker_id)
        if worker and worker.status != WorkerStatus.DEAD.value:
            worker.last_heartbeat = utc_now()
            worker.current_job_id = current_job_id
            self.session.flush()
        return worker

    def set_status(self, worker_id: str, status: WorkerStatus) -> Optional[Worker]:
        """Sets worker status (e.g. ACTIVE, STOPPING, STOPPED, DEAD)."""
        worker = self.session.get(Worker, worker_id)
        if worker:
            worker.status = status.value
            if status in (WorkerStatus.STOPPED, WorkerStatus.DEAD):
                worker.current_job_id = None
            self.session.flush()
        return worker

    def increment_counters(self, worker_id: str, success: bool = True) -> None:
        """Increments jobs_processed or jobs_failed count for worker."""
        worker = self.session.get(Worker, worker_id)
        if worker:
            if success:
                worker.jobs_processed += 1
            else:
                worker.jobs_failed += 1
            self.session.flush()

    def get_by_id(self, worker_id: str) -> Optional[Worker]:
        """Fetch worker by ID."""
        return self.session.get(Worker, worker_id)

    def list_all(self, status: Optional[str] = None) -> List[Worker]:
        """List all registered workers, optionally filtered by status."""
        query = self.session.query(Worker)
        if status:
            query = query.filter(Worker.status == status)
        return query.order_by(Worker.started_at.desc()).all()

    def find_stale_workers(self, recovery_timeout_seconds: float) -> List[Worker]:
        """
        Finds active workers whose last heartbeat exceeds recovery_timeout_seconds.

        CRASH RECOVERY LOGIC:
        If a worker process receives SIGKILL (or host crashes), it leaves its DB status
        as ACTIVE or STOPPING, but stops sending heartbeats. Any worker with:
          status IN ('active', 'stopping')
          AND last_heartbeat < (NOW - recovery_timeout_seconds)
        is classified as DEAD and subject to crash recovery.
        """
        now = utc_now()
        threshold = now - timedelta(seconds=recovery_timeout_seconds)

        return (
            self.session.query(Worker)
            .filter(
                Worker.status.in_([WorkerStatus.ACTIVE.value, WorkerStatus.STOPPING.value]),
                Worker.last_heartbeat < threshold,
            )
            .all()
        )
