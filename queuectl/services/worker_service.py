"""
QueueCTL Worker Management Service Module.

Provides functions to start worker processes and request cross-terminal worker termination.
"""

import os
import signal
from typing import Dict, List, Optional, Any
import psutil

from queuectl.database.connection import DatabaseManager
from queuectl.models.enums import WorkerStatus
from queuectl.repositories.worker_repository import WorkerRepository
from queuectl.utils.logger import get_logger
from queuectl.workers.runner import WorkerRunner

logger = get_logger("queuectl.worker_service")


class WorkerService:
    """Service layer for worker process management and cross-terminal termination."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def start_worker(self, worker_id: Optional[str] = None):
        """Launches worker process in current terminal."""
        runner = WorkerRunner(self.db_manager.db_path, worker_id=worker_id)
        runner.start()

    def stop_worker(self, worker_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Requests worker process stop across terminals.

        CROSS-TERMINAL WORKER STOP EXPLANATION FOR INTERVIEW DEFENSE:
        -------------------------------------------------------------
        1. Mechanism: Database Registry + Signal Broadcasting.
        2. When `queuectl worker stop [worker_id]` is executed in ANY terminal:
           a. Updates the target worker record's status to 'stopping' in SQLite database.
           b. The worker's heartbeat loop (or main loop) reads its DB status on the next tick
              (within 1-5 seconds) and sets its graceful shutdown flag.
           c. Additionally, if the worker process is running on the local host,
              we send SIGINT signal to its registered PID via OS process API.
        3. Advantage over raw PID signals alone: Works seamlessly across separate shell sessions,
           terminals, or container environments sharing the SQLite database.
        """
        stopped_info = []

        with self.db_manager.session() as session:
            repo = WorkerRepository(session)
            if worker_id:
                target_workers = [w for w in repo.list_all() if w.id == worker_id and w.status in (WorkerStatus.ACTIVE.value, WorkerStatus.STOPPING.value)]
            else:
                target_workers = repo.list_all(status=WorkerStatus.ACTIVE.value)

            for w in target_workers:
                logger.info(f"Requesting stop for Worker '{w.id}' (PID {w.pid})...")
                repo.set_status(w.id, WorkerStatus.STOPPING)
                
                # Attempt direct OS signal to PID if on same host
                try:
                    if psutil.pid_exists(w.pid):
                        proc = psutil.Process(w.pid)
                        proc.send_signal(signal.SIGINT)
                        logger.info(f"Sent SIGINT to process PID {w.pid}.")
                except Exception as err:
                    logger.debug(f"Could not send signal directly to PID {w.pid}: {err}")

                stopped_info.append({
                    "id": w.id,
                    "pid": w.pid,
                    "status": WorkerStatus.STOPPING.value,
                })

        return stopped_info

    def list_workers(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists all registered workers."""
        with self.db_manager.session() as session:
            repo = WorkerRepository(session)
            workers = repo.list_all(status=status)
            return [w.to_dict() for w in workers]
