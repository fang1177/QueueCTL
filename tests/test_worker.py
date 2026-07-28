"""
QueueCTL Worker Management Unit Tests.

Tests worker lifecycle registration, worker listing, and cross-terminal stop signals.
"""

import pytest
from queuectl.models.enums import WorkerStatus
from queuectl.repositories.worker_repository import WorkerRepository


def test_worker_registration_and_list(db_manager, worker_service):
    """Tests worker process registration and query list."""
    with db_manager.session() as session:
        repo = WorkerRepository(session)
        repo.register("w1", pid=1001, hostname="host1")
        repo.register("w2", pid=1002, hostname="host1")

    workers = worker_service.list_workers()
    assert len(workers) == 2
    ids = {w["id"] for w in workers}
    assert "w1" in ids
    assert "w2" in ids


def test_worker_stop_cross_terminal(db_manager, worker_service):
    """Tests sending cross-terminal stop signal to worker database records."""
    with db_manager.session() as session:
        repo = WorkerRepository(session)
        repo.register("w-stop-target", pid=8888, hostname="host1")

    stopped = worker_service.stop_worker(worker_id="w-stop-target")
    assert len(stopped) == 1
    assert stopped[0]["id"] == "w-stop-target"
    assert stopped[0]["status"] == WorkerStatus.STOPPING.value

    # Verify status in database
    with db_manager.session() as session:
        repo = WorkerRepository(session)
        w = repo.get_by_id("w-stop-target")
        assert w.status == WorkerStatus.STOPPING.value
