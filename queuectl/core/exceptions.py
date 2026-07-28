"""
QueueCTL Exceptions Module.

Defines standard domain exceptions for error handling.
"""


class QueueCTLError(Exception):
    """Base exception for QueueCTL domain errors."""
    pass


class JobNotFoundError(QueueCTLError):
    """Raised when requested job ID does not exist."""
    def __init__(self, job_id: str):
        super().__init__(f"Job with ID '{job_id}' not found.")
        self.job_id = job_id


class InvalidStateTransitionError(QueueCTLError):
    """Raised when an illegal job state transition is attempted."""
    def __init__(self, current_state: str, target_state: str):
        super().__init__(f"Invalid state transition from '{current_state}' to '{target_state}'.")
        self.current_state = current_state
        self.target_state = target_state


class WorkerNotFoundError(QueueCTLError):
    """Raised when requested worker ID does not exist."""
    def __init__(self, worker_id: str):
        super().__init__(f"Worker with ID '{worker_id}' not found.")
        self.worker_id = worker_id


class ConfigError(QueueCTLError):
    """Raised when a configuration key or value is invalid."""
    pass


class AtomicClaimError(QueueCTLError):
    """Raised when atomic job claiming fails due to transaction contention."""
    pass
