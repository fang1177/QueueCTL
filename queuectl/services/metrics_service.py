"""
QueueCTL Metrics Service Module.

Aggregates operational metrics, worker counts, job distributions,
and queue performance statistics.
"""

from typing import Any, Dict
from queuectl.database.connection import DatabaseManager
from queuectl.repositories.job_repository import JobRepository
from queuectl.repositories.worker_repository import WorkerRepository
from queuectl.services.config_service import ConfigService


class MetricsService:
    """Service layer for gathering system metrics and queue status."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.config_service = ConfigService(db_manager)

    def get_system_status(self) -> Dict[str, Any]:
        """
        Returns complete system status overview.

        Includes:
        - Job distribution counts (Total, Pending, Processing, Completed, Failed, Dead)
        - Worker status breakdown (Active, Stopping, Stopped, Dead)
        - Active Configuration overview
        """
        with self.db_manager.session() as session:
            job_repo = JobRepository(session)
            worker_repo = WorkerRepository(session)

            job_counts = job_repo.get_job_counts()
            workers = worker_repo.list_all()

            active_workers = [w.to_dict() for w in workers if w.status == "active"]
            stopping_workers = [w.to_dict() for w in workers if w.status == "stopping"]
            dead_workers = [w.to_dict() for w in workers if w.status == "dead"]

            configs = self.config_service.get_all_configs()

            return {
                "jobs": job_counts,
                "workers": {
                    "total_registered": len(workers),
                    "active_count": len(active_workers),
                    "stopping_count": len(stopping_workers),
                    "dead_count": len(dead_workers),
                    "active": active_workers,
                },
                "config": configs,
            }
