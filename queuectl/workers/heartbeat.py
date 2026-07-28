"""
QueueCTL Worker Heartbeat Module.

Runs background heartbeat thread to update worker status in database
and listen for cross-terminal stop requests.
"""

import threading
import time
from typing import Callable, Optional

from queuectl.database.connection import DatabaseManager
from queuectl.models.enums import WorkerStatus
from queuectl.repositories.worker_repository import WorkerRepository
from queuectl.utils.logger import get_logger

logger = get_logger("queuectl.heartbeat")


class HeartbeatDaemon:
    """Threaded heartbeat manager for worker processes."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        worker_id: str,
        interval_seconds: float = 5.0,
        stop_requested_callback: Optional[Callable[[], None]] = None
    ):
        self.db_manager = db_manager
        self.worker_id = worker_id
        self.interval_seconds = interval_seconds
        self.stop_requested_callback = stop_requested_callback
        
        self.current_job_id: Optional[str] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the heartbeat thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_heartbeat_loop,
            name=f"HeartbeatThread-{self.worker_id}",
            daemon=True
        )
        self._thread.start()
        logger.debug(f"Heartbeat thread started for worker '{self.worker_id}'.")

    def stop(self):
        """Stops the heartbeat thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.debug(f"Heartbeat thread stopped for worker '{self.worker_id}'.")

    def set_current_job(self, job_id: Optional[str]):
        """Sets the job currently being executed by the worker."""
        self.current_job_id = job_id

    def _run_heartbeat_loop(self):
        while not self._stop_event.is_set():
            try:
                with self.db_manager.session() as session:
                    repo = WorkerRepository(session)
                    worker = repo.update_heartbeat(self.worker_id, self.current_job_id)
                    
                    # Check if stop signal was flagged in DB by cross-terminal command
                    if worker and worker.status == WorkerStatus.STOPPING.value:
                        logger.info(f"Worker '{self.worker_id}' received STOPPING request from database.")
                        if self.stop_requested_callback:
                            self.stop_requested_callback()
            except Exception as e:
                logger.error(f"Error sending heartbeat for worker '{self.worker_id}': {e}")

            # Sleep in small increments for responsive thread termination
            self._stop_event.wait(self.interval_seconds)
