"""
QueueCTL FastAPI Web Dashboard Integration Tests.

Tests REST API endpoints served by the web monitoring dashboard.
"""

import os
import pytest
from fastapi.testclient import TestClient
from queuectl.web.app import app


@pytest.fixture
def api_client(temp_db_path):
    """Sets environment DB path and provides FastAPI TestClient."""
    os.environ["QUEUECTL_DB_PATH"] = temp_db_path
    client = TestClient(app)
    return client


def test_dashboard_root_html(api_client):
    """Tests GET / returns HTML dashboard."""
    response = api_client.get("/")
    assert response.status_code == 200
    assert "QueueCTL Live Dashboard" in response.text


def test_dashboard_api_status(api_client):
    """Tests GET /api/status endpoint."""
    response = api_client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "workers" in data


def test_dashboard_api_jobs(api_client):
    """Tests GET /api/jobs endpoint."""
    response = api_client.get("/api/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_dashboard_api_workers(api_client):
    """Tests GET /api/workers endpoint."""
    response = api_client.get("/api/workers")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
