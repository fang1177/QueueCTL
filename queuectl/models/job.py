"""
QueueCTL Job Model and Schema Module.

Defines SQLAlchemy 2.0 ORM model for `jobs` table and Pydantic schemas.
"""

from datetime import datetime
import uuid
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from queuectl.database.connection import Base
from queuectl.models.enums import JobState
from queuectl.utils.time_utils import utc_now


class Job(Base):
    """SQLAlchemy ORM Model for background jobs."""
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default=JobState.PENDING.value, index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    backoff_base: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)
    timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    worker_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # Composite index specifically optimized for atomic job claiming query
        Index("idx_jobs_claim", "state", "scheduled_at", "priority", "created_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "command": self.command,
            "state": self.state,
            "priority": self.priority,
            "attempts": self.attempts,
            "max_retries": self.max_retries,
            "backoff_base": self.backoff_base,
            "timeout": self.timeout,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "worker_id": self.worker_id,
            "error_message": self.error_message,
            "output": self.output,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class JobCreate(BaseModel):
    """Pydantic model for job creation validation."""
    name: str = Field(..., min_length=1, max_length=255, description="Human-readable job name")
    command: str = Field(..., min_length=1, description="Shell command to execute")
    priority: int = Field(default=0, ge=-100, le=100, description="Job priority (higher runs first)")
    max_retries: int = Field(default=3, ge=0, le=20, description="Max retries before sending to DLQ")
    backoff_base: float = Field(default=2.0, ge=1.0, le=10.0, description="Exponential backoff base multiplier")
    timeout: int = Field(default=60, ge=1, le=86400, description="Timeout limit in seconds")
    delay_seconds: Optional[int] = Field(default=None, ge=0, description="Delay execution by N seconds")


class JobResponse(BaseModel):
    """Pydantic model for job response serialization."""
    id: str
    name: str
    command: str
    state: str
    priority: int
    attempts: int
    max_retries: int
    backoff_base: float
    timeout: int
    scheduled_at: Optional[str] = None
    worker_id: Optional[str] = None
    error_message: Optional[str] = None
    output: Optional[str] = None
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
