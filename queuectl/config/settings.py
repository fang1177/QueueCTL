"""
QueueCTL System Settings Module.

Manages application configurations with support for YAML files,
SQLite runtime overrides, and sensible production defaults.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from pydantic import BaseModel, Field

DEFAULT_DB_DIR = Path.home() / ".queuectl"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "queuectl.db"
DEFAULT_CONFIG_PATH = DEFAULT_DB_DIR / "config.yaml"


class QueueCTLSettings(BaseModel):
    """Pydantic model representing QueueCTL configuration schema."""
    
    db_path: str = Field(
        default_factory=lambda: str(DEFAULT_DB_PATH),
        description="Path to SQLite database file"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=20,
        description="Default maximum retry attempts for failed jobs"
    )
    backoff_base: float = Field(
        default=2.0,
        ge=1.0,
        le=10.0,
        description="Base multiplier for exponential backoff delay (base ^ attempt seconds)"
    )
    heartbeat_interval: float = Field(
        default=5.0,
        ge=1.0,
        le=60.0,
        description="Interval in seconds between worker heartbeat updates"
    )
    recovery_timeout: float = Field(
        default=30.0,
        ge=5.0,
        le=300.0,
        description="Heartbeat silence duration in seconds after which worker is considered dead (<60s requirement)"
    )
    default_job_timeout: int = Field(
        default=60,
        ge=1,
        le=86400,
        description="Default timeout in seconds for job execution"
    )
    poll_interval: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Worker polling interval in seconds when queue is idle"
    )
    log_dir: str = Field(
        default_factory=lambda: str(DEFAULT_DB_DIR / "logs"),
        description="Directory for log files"
    )


def load_yaml_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Loads configuration dictionary from YAML file if exists."""
    config_file = path or DEFAULT_CONFIG_PATH
    if not config_file.exists():
        return {}
    
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_yaml_config(settings: QueueCTLSettings, path: Optional[Path] = None) -> None:
    """Saves settings to YAML configuration file."""
    config_file = path or DEFAULT_CONFIG_PATH
    config_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(settings.model_dump(), f, default_flow_style=False)


def get_settings(db_path_override: Optional[str] = None) -> QueueCTLSettings:
    """Instantiates settings incorporating defaults and environment/YAML settings."""
    yaml_data = load_yaml_config()
    if db_path_override:
        yaml_data["db_path"] = db_path_override
    
    return QueueCTLSettings(**yaml_data)
