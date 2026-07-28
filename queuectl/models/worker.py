"""
QueueCTL Worker Model Module.

Defines SQLAlchemy ORM model for worker registry and process tracking.
"""

from datetime import datetime
import os
import socket
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from queuectl.database.connection import Base
from queuectl.models.enums import WorkerStatus
from queuectl.utils.time_utils import utc_now


class Worker(Base):
    """SQLAlchemy ORM Model for active and historical workers."""
    __tablename__ = "workers"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    pid: Mapped[int] = mapped_column(Integer, nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, default=lambda: socket.gethostname())
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=WorkerStatus.ACTIVE.value, index=True)
    
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    
    current_job_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    jobs_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        return {
            "id": self.id,
            "pid": self.pid,
            "hostname": self.hostname,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "current_job_id": self.current_job_id,
            "jobs_processed": self.jobs_processed,
            "jobs_failed": self.jobs_failed,
        }


class WorkerResponse(BaseModel):
    """Pydantic model for worker serialization."""
    id: str
    pid: int
    hostname: str
    status: str
    started_at: str
    last_heartbeat: str
    current_job_id: Optional[str] = None
    jobs_processed: int
    jobs_failed: int
