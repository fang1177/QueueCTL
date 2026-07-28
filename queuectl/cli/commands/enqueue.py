"""
QueueCTL CLI Enqueue Command.

Enqueues background jobs with custom priority, retries, backoff, and execution options.
"""

from typing import Optional
import typer
from queuectl.cli.formatter import print_error, print_success
from queuectl.config.settings import get_settings
from queuectl.database.connection import get_db_manager
from queuectl.models.job import JobCreate
from queuectl.services.queue_service import QueueService


def enqueue_command(
    name: str = typer.Option(..., "--name", "-n", help="Human-readable job name"),
    command: str = typer.Option(..., "--command", "-c", help="Shell command string to execute"),
    priority: int = typer.Option(0, "--priority", "-p", help="Job priority (higher value runs first)"),
    max_retries: Optional[int] = typer.Option(None, "--max-retries", "-r", help="Max retry attempts before sending to DLQ"),
    backoff_base: Optional[float] = typer.Option(None, "--backoff-base", "-b", help="Exponential backoff base multiplier"),
    timeout: Optional[int] = typer.Option(None, "--timeout", "-t", help="Timeout limit in seconds"),
    delay: Optional[int] = typer.Option(None, "--delay", help="Delay execution by N seconds"),
    db_path: Optional[str] = typer.Option(None, "--db-path", "-d", help="Path to SQLite database file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
):
    """Enqueues a new background job into QueueCTL."""
    try:
        settings = get_settings(db_path)
        db_manager = get_db_manager(settings.db_path)
        service = QueueService(db_manager)

        job_create = JobCreate(
            name=name,
            command=command,
            priority=priority,
            max_retries=max_retries if max_retries is not None else settings.max_retries,
            backoff_base=backoff_base if backoff_base is not None else settings.backoff_base,
            timeout=timeout if timeout is not None else settings.default_job_timeout,
            delay_seconds=delay,
        )

        job_dict = service.enqueue(job_create)
        
        msg = f"Job '{job_dict['name']}' (ID: {job_dict['id']}) enqueued successfully."
        print_success(msg, is_json=json_output, json_data=job_dict)

    except Exception as e:
        print_error(f"Failed to enqueue job: {e}", is_json=json_output)
