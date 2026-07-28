"""
QueueCTL Database Migration & Initialization Module.

Creates tables and populates default runtime configurations.
"""

from typing import Optional
from queuectl.config.settings import QueueCTLSettings, get_settings
from queuectl.database.connection import get_db_manager
from queuectl.models.config import ConfigItem
from queuectl.utils.logger import get_logger

logger = get_logger("queuectl.migrations")


def init_db(db_path: Optional[str] = None) -> str:
    """Initializes the database schema and seeds default configuration values."""
    settings = get_settings(db_path)
    db_manager = get_db_manager(settings.db_path)

    logger.info(f"Initializing database at: {settings.db_path}")
    db_manager.create_tables()

    # Seed default runtime configuration items if not present
    default_configs = {
        "max_retries": str(settings.max_retries),
        "backoff_base": str(settings.backoff_base),
        "heartbeat_interval": str(settings.heartbeat_interval),
        "recovery_timeout": str(settings.recovery_timeout),
        "default_job_timeout": str(settings.default_job_timeout),
    }

    with db_manager.session() as session:
        for key, value in default_configs.items():
            existing = session.query(ConfigItem).filter(ConfigItem.key == key).first()
            if not existing:
                session.add(ConfigItem(key=key, value=value))

    logger.info("Database initialized successfully with default tables and configuration.")
    return settings.db_path
