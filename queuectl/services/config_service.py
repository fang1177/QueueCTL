"""
QueueCTL Configuration Service Module.

Provides business logic and type validation for configuration settings.
"""

from typing import Any, Dict, Optional
from queuectl.config.settings import QueueCTLSettings, get_settings
from queuectl.core.exceptions import ConfigError
from queuectl.database.connection import DatabaseManager
from queuectl.repositories.config_repository import ConfigRepository


class ConfigService:
    """Service layer for dynamic system configurations."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def get_config(self, key: str) -> str:
        """Retrieves config value, falling back to file/default settings."""
        with self.db_manager.session() as session:
            repo = ConfigRepository(session)
            val = repo.get(key)
            if val is not None:
                return val

        # Fallback to defaults
        settings = get_settings(self.db_manager.db_path)
        if hasattr(settings, key):
            return str(getattr(settings, key))

        raise ConfigError(f"Unknown configuration key: '{key}'")

    def set_config(self, key: str, value: str) -> Dict[str, str]:
        """Validates and sets dynamic runtime configuration value."""
        # Validation checks
        if key in ("max_retries", "default_job_timeout"):
            try:
                v_int = int(value)
                if v_int < 0:
                    raise ValueError()
            except ValueError:
                raise ConfigError(f"Key '{key}' must be a non-negative integer.")
        elif key in ("backoff_base", "heartbeat_interval", "recovery_timeout", "poll_interval"):
            try:
                v_float = float(value)
                if v_float <= 0:
                    raise ValueError()
            except ValueError:
                raise ConfigError(f"Key '{key}' must be a positive float.")
        else:
            settings = get_settings(self.db_manager.db_path)
            if not hasattr(settings, key):
                raise ConfigError(f"Unsupported configuration key: '{key}'")

        with self.db_manager.session() as session:
            repo = ConfigRepository(session)
            item = repo.set(key, str(value))
            return item.to_dict()

    def get_all_configs(self) -> Dict[str, Any]:
        """Returns consolidated configuration dictionary (Defaults + Overrides)."""
        settings = get_settings(self.db_manager.db_path)
        consolidated = settings.model_dump()

        with self.db_manager.session() as session:
            repo = ConfigRepository(session)
            db_configs = repo.get_all()
            for k, v in db_configs.items():
                if k in consolidated:
                    # Attempt type conversion to match settings schema type
                    orig_type = type(consolidated[k])
                    try:
                        consolidated[k] = orig_type(v)
                    except Exception:
                        consolidated[k] = v

        return consolidated
