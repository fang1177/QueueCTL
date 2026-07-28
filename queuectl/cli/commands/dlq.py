"""
QueueCTL CLI Dead Letter Queue (DLQ) Commands Module.

Provides subcommands for listing dead-lettered jobs and retrying them.
"""

from typing import Optional
import typer
from queuectl.cli.formatter import print_error, print_job_table, print_success
from queuectl.config.settings import get_settings
from queuectl.database.connection import get_db_manager
from queuectl.models.enums import JobState
from queuectl.services.queue_service import QueueService

dlq_app = typer.Typer(help="Manage Dead Letter Queue (DLQ) jobs")


@dlq_app.command("list")
def dlq_list_command(
    limit: int = typer.Option(50, "--limit", "-l", help="Maximum number of dead jobs to display"),
    db_path: Optional[str] = typer.Option(None, "--db-path", "-d", help="Path to SQLite database file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
):
    """Lists dead jobs currently in the Dead Letter Queue (DLQ)."""
    try:
        settings = get_settings(db_path)
        db_manager = get_db_manager(settings.db_path)
        service = QueueService(db_manager)

        dead_jobs = service.list_jobs(state=JobState.DEAD.value, limit=limit)
        print_job_table(dead_jobs, title="Dead Letter Queue (DLQ)", is_json=json_output)
    except Exception as e:
        print_error(f"Failed to list DLQ jobs: {e}", is_json=json_output)


@dlq_app.command("retry")
def dlq_retry_command(
    job_id: str = typer.Argument(..., help="ID of the dead job to retry"),
    db_path: Optional[str] = typer.Option(None, "--db-path", "-d", help="Path to SQLite database file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
):
    """Retries a dead job by resetting attempts to 0 and state to pending."""
    try:
        settings = get_settings(db_path)
        db_manager = get_db_manager(settings.db_path)
        service = QueueService(db_manager)

        job_dict = service.retry_dlq_job(job_id)
        msg = f"Dead Job '{job_id}' reset successfully. Re-enqueued with 0 attempts."
        print_success(msg, is_json=json_output, json_data=job_dict)
    except Exception as e:
        print_error(f"Failed to retry DLQ job: {e}", is_json=json_output)
