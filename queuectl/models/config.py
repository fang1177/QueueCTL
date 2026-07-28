"""
QueueCTL Configuration Model Module.

Defines SQLAlchemy ORM model for dynamic configuration items.
"""

from datetime import datetime
from typing import Any, Dict
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from queuectl.database.connection import Base
from queuectl.utils.time_utils import utc_now


class ConfigItem(Base):
    """SQLAlchemy ORM Model for runtime system configurations."""
    __tablename__ = "configuration"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        return {
            "key": self.key,
            "value": self.value,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
