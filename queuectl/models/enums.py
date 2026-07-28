"""
QueueCTL Domain Enums.

Defines status states for jobs and workers.
"""

from enum import Enum


class JobState(str, Enum):
    """Job status state machine enum."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"

    @classmethod
    def is_valid_transition(cls, current: "JobState", target: "JobState") -> bool:
        """Validates job state transition lifecycle."""
        valid_transitions = {
            cls.PENDING: {cls.PROCESSING, cls.DEAD},
            cls.PROCESSING: {cls.COMPLETED, cls.FAILED, cls.DEAD, cls.PENDING},  # PENDING allowed for crash recovery
            cls.FAILED: {cls.PENDING, cls.DEAD},  # PENDING allowed for retry, DEAD for max retries reached
            cls.COMPLETED: set(),
            cls.DEAD: {cls.PENDING},  # PENDING allowed for DLQ manually requested retry
        }
        return target in valid_transitions.get(current, set())


class WorkerStatus(str, Enum):
    """Worker process status enum."""
    ACTIVE = "active"
    STOPPING = "stopping"
    STOPPED = "stopped"
    DEAD = "dead"
