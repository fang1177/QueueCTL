"""
QueueCTL Worker Runner Module.

Executes the main worker event loop: registering processes, polling jobs atomically,
executing shell commands, recording execution logs, managing heartbeats,
handling errors/retries/DLQ, and performing graceful shutdowns.
"""

import os
import socket
import time
import uuid
from typing import Optional

from queuectl.config.settings import get_settings
from queuectl.core.executor import CommandExecutor
from queuectl.core.signals import SignalHandler
from queuectl.database.connection import DatabaseManager, get_db_manager
from queuectl.models.enums import JobState, WorkerStatus
from queuectl.repositories.job_repository import JobRepository
from queuectl.repositories.worker_repository import WorkerRepository
from queuectl.services.config_service import ConfigService
from queuectl.services.recovery_service import CrashRecoveryService
from queuectl.utils.logger import get_logger
from queuectl.workers.heartbeat import HeartbeatDaemon

logger = get_logger("queuectl.worker")


class WorkerRunner:
    """Worker process event loop and execution manager."""

    def __init__(self, db_path: str, worker_id: Optional[str] = None):
        self.db_path = db_path
        self.worker_id = worker_id or f"worker-{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self.db_manager = get_db_manager(db_path)
        self.config_service = ConfigService(self.db_manager)
        self.recovery_service = CrashRecoveryService(self.db_manager)
        
        self.signal_handler = SignalHandler()
        self.heartbeat_daemon: Optional[HeartbeatDaemon] = None
        self.is_running = False

    def start(self):
        """Starts the worker process event loop."""
        pid = os.getpid()
        hostname = socket.gethostname()
        logger.info(f"Starting Worker process '{self.worker_id}' (PID {pid} on {hostname})...")

        # Step 1: Register worker in DB
        with self.db_manager.session() as session:
            worker_repo = WorkerRepository(session)
            worker_repo.register(self.worker_id, pid, hostname)

        # Step 2: Register signal handlers for graceful shutdown
        def request_stop():
            self.is_running = False

        self.signal_handler.register_signals(on_shutdown_callback=request_stop)

        # Step 3: Start Heartbeat background thread
        configs = self.config_service.get_all_configs()
        hb_interval = float(configs.get("heartbeat_interval", 5.0))
        
        self.heartbeat_daemon = HeartbeatDaemon(
            db_manager=self.db_manager,
            worker_id=self.worker_id,
            interval_seconds=hb_interval,
            stop_requested_callback=request_stop,
        )
        self.heartbeat_daemon.start()

        self.is_running = True
        poll_interval = float(configs.get("poll_interval", 1.0))

        logger.info(f"Worker '{self.worker_id}' initialized. Listening for jobs...")

        try:
            while self.is_running and not self.signal_handler.shutdown_requested:
                # Step 4a: Run periodic crash recovery check to detect dead workers/jobs
                try:
                    self.recovery_service.recover_stale_workers_and_jobs()
                except Exception as rec_err:
                    logger.error(f"Error during crash recovery scan: {rec_err}")

                # Step 4b: Atomically claim next eligible pending job
                job = None
                with self.db_manager.session() as session:
                    job_repo = JobRepository(session)
                    job = job_repo.claim_next_job(self.worker_id)

                if job:
                    logger.info(f"Claimed Job '{job.id}' ('{job.name}') | Command: '{job.command}' | Attempt: {job.attempts + 1}/{job.max_retries}")
                    if self.heartbeat_daemon:
                        self.heartbeat_daemon.set_current_job(job.id)

                    # Step 4c: Execute job subprocess command
                    exec_result = CommandExecutor.execute(job.command, timeout_seconds=job.timeout)

                    # Step 4d: Handle execution result (Success vs Failure)
                    exit_code = exec_result["exit_code"]
                    stdout = exec_result["stdout"]
                    stderr = exec_result["stderr"]
                    duration_ms = exec_result["duration_ms"]
                    error_msg = exec_result["error_message"]

                    with self.db_manager.session() as session:
                        job_repo = JobRepository(session)
                        worker_repo = WorkerRepository(session)

                        if exit_code == 0:
                            logger.info(f"Job '{job.id}' succeeded in {duration_ms:.1f}ms.")
                            job_repo.mark_completed(job.id, output=stdout)
                            job_repo.log_execution(
                                job_id=job.id,
                                worker_id=self.worker_id,
                                attempt=job.attempts + 1,
                                status=JobState.COMPLETED.value,
                                exit_code=exit_code,
                                stdout=stdout,
                                stderr=stderr,
                                duration_ms=duration_ms,
                            )
                            worker_repo.increment_counters(self.worker_id, success=True)
                        else:
                            logger.warning(f"Job '{job.id}' failed (Exit Code {exit_code}). Error: {error_msg}")
                            updated_job = job_repo.mark_failed(job.id, error_message=error_msg, output=stdout)
                            
                            status_str = updated_job.state
                            job_repo.log_execution(
                                job_id=job.id,
                                worker_id=self.worker_id,
                                attempt=job.attempts,
                                status=status_str,
                                exit_code=exit_code,
                                stdout=stdout,
                                stderr=stderr,
                                error_message=error_msg,
                                duration_ms=duration_ms,
                            )
                            worker_repo.increment_counters(self.worker_id, success=False)

                    if self.heartbeat_daemon:
                        self.heartbeat_daemon.set_current_job(None)

                else:
                    # No job pending, idle sleep
                    time.sleep(poll_interval)

        except Exception as err:
            logger.critical(f"Unhandled error in worker loop: {err}", exc_info=True)
        finally:
            self._cleanup()

    def _cleanup(self):
        """Performs clean shutdown and updates worker status in DB."""
        logger.info(f"Shutting down worker '{self.worker_id}'...")
        
        if self.heartbeat_daemon:
            self.heartbeat_daemon.stop()

        try:
            with self.db_manager.session() as session:
                worker_repo = WorkerRepository(session)
                worker_repo.set_status(self.worker_id, WorkerStatus.STOPPED)
        except Exception as e:
            logger.error(f"Error marking worker stopped: {e}")

        logger.info(f"Worker '{self.worker_id}' shutdown complete.")
