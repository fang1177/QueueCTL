"""
QueueCTL CLI End-to-End Command Tests.

Tests CLI command invocation, arguments, options, and JSON output formatting.
"""

import json
import pytest
from typer.testing import CliRunner
from queuectl.cli.main import app

runner = CliRunner()


def test_cli_version():
    """Tests queuectl version command."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "QueueCTL version" in result.stdout


def test_cli_init(temp_db_path):
    """Tests queuectl init command with --json flag."""
    result = runner.invoke(app, ["init", "--db-path", temp_db_path, "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["status"] == "success"
    assert data["db_path"] == temp_db_path


def test_cli_enqueue_and_list_json(temp_db_path):
    """Tests queuectl enqueue and queuectl list commands with --json output."""
    # Enqueue job
    enq_result = runner.invoke(app, [
        "enqueue",
        "--name", "CLI Job",
        "--command", "echo 'cli test'",
        "--priority", "5",
        "--db-path", temp_db_path,
        "--json"
    ])
    assert enq_result.exit_code == 0
    job_data = json.loads(enq_result.stdout)
    assert job_data["name"] == "CLI Job"
    assert job_data["priority"] == 5

    # List jobs
    list_result = runner.invoke(app, ["list", "--db-path", temp_db_path, "--json"])
    assert list_result.exit_code == 0
    jobs_list = json.loads(list_result.stdout)
    assert len(jobs_list) == 1
    assert jobs_list[0]["name"] == "CLI Job"


def test_cli_status_json(temp_db_path):
    """Tests queuectl status command with --json output."""
    result = runner.invoke(app, ["status", "--db-path", temp_db_path, "--json"])
    assert result.exit_code == 0
    status = json.loads(result.stdout)
    assert "jobs" in status
    assert "workers" in status
    assert "config" in status


def test_cli_config_set_show_json(temp_db_path):
    """Tests queuectl config set and show commands."""
    set_res = runner.invoke(app, ["config", "set", "max_retries", "10", "--db-path", temp_db_path, "--json"])
    assert set_res.exit_code == 0
    
    show_res = runner.invoke(app, ["config", "show", "--db-path", temp_db_path, "--json"])
    assert show_res.exit_code == 0
    configs = json.loads(show_res.stdout)
    assert configs["max_retries"] == 10
