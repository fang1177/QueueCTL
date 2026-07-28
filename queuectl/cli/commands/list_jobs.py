"""
QueueCTL CLI List Jobs Command.

Lists background jobs with optional state filtering and JSON output.
"""

from typing import Optional
import typer
from queuectl.cli.formatter import print_error, print_job_table
from queuectl.config.settings import get_settings
from queuectl.database.connection import get_db_manager
from queuectl.services.queue_service import QueueService


def list_jobs_command(
    state: Optional[str] = typer.Option(None, "--state", "-s", help="Filter jobs by state (pending, processing, completed, failed, dead)"),
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of jobs to display"),
    offset: int = typer.Option(0, "--offset", help="Pagination offset"),
    db_path: Optional[str] = typer.Option(None, "--db-path", "-d", help="Path to SQLite database file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
):
    """Lists jobs in the queue with optional filtering."""
    try:
        settings = get_settings(db_path)
        db_manager = get_db_manager(settings.db_path)
        service = QueueService(db_manager)

        jobs = service.list_jobs(state=state, limit=limit, offset=offset)
        title = f"Jobs ({state.upper()})" if state else "All Jobs"
        print_job_table(jobs, title=title, is_json=json_output)
    except Exception as e:
        print_error(f"Failed to list jobs: {e}", is_json=json_output)
