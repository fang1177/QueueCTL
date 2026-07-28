"""
Pytest Fixtures Module for QueueCTL Test Suite.

Provides isolated temporary SQLite databases for each test session.
"""

import os
import tempfile
import pytest
from pathlib import Path

from queuectl.database.connection import DatabaseManager, get_db_manager
from queuectl.database.migrations import init_db
from queuectl.services.config_service import ConfigService
from queuectl.services.queue_service import QueueService
from queuectl.services.worker_service import WorkerService


@pytest.fixture
def temp_db_path(tmp_path) -> str:
    """Creates a temporary SQLite database file for testing."""
    db_file = tmp_path / "test_queuectl.db"
    path_str = str(db_file)
    init_db(path_str)
    return path_str


@pytest.fixture
def db_manager(temp_db_path) -> DatabaseManager:
    """Provides initialized DatabaseManager instance."""
    return get_db_manager(temp_db_path)


@pytest.fixture
def queue_service(db_manager) -> QueueService:
    """Provides QueueService instance."""
    return QueueService(db_manager)


@pytest.fixture
def worker_service(db_manager) -> WorkerService:
    """Provides WorkerService instance."""
    return WorkerService(db_manager)


@pytest.fixture
def config_service(db_manager) -> ConfigService:
    """Provides ConfigService instance."""
    return ConfigService(db_manager)
