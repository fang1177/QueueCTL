"""
QueueCTL CLI Worker Commands Module.

Provides subcommands for starting and stopping worker processes.
"""

from typing import Optional
import typer
from queuectl.cli.formatter import print_error, print_success, print_worker_table
from queuectl.config.settings import get_settings
from queuectl.database.connection import get_db_manager
from queuectl.services.worker_service import WorkerService

worker_app = typer.Typer(help="Manage QueueCTL worker processes")


@worker_app.command("start")
def start_worker_command(
    worker_id: Optional[str] = typer.Option(None, "--id", help="Custom worker process ID"),
    db_path: Optional[str] = typer.Option(None, "--db-path", "-d", help="Path to SQLite database file"),
):
    """Starts a QueueCTL worker process in the foreground."""
    try:
        settings = get_settings(db_path)
        db_manager = get_db_manager(settings.db_path)
        db_manager.create_tables()

        service = WorkerService(db_manager)
        service.start_worker(worker_id=worker_id)
    except Exception as e:
        print_error(f"Worker execution failed: {e}")


@worker_app.command("stop")
def stop_worker_command(
    worker_id: Optional[str] = typer.Argument(None, help="Worker ID to stop (stops all active workers if omitted)"),
    db_path: Optional[str] = typer.Option(None, "--db-path", "-d", help="Path to SQLite database file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
):
    """Requests graceful shutdown for worker processes across terminals."""
    try:
        settings = get_settings(db_path)
        db_manager = get_db_manager(settings.db_path)

        service = WorkerService(db_manager)
        stopped_list = service.stop_worker(worker_id=worker_id)

        if not stopped_list:
            msg = f"No active worker found with ID '{worker_id}'." if worker_id else "No active workers found."
            print_error(msg, is_json=json_output)
            return

        msg = f"Stop request sent to {len(stopped_list)} worker(s)."
        print_success(msg, is_json=json_output, json_data={"status": "success", "stopped_workers": stopped_list})

    except Exception as e:
        print_error(f"Failed to stop worker: {e}", is_json=json_output)


@worker_app.command("list")
def list_workers_command(
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter workers by status (active, stopping, stopped, dead)"),
    db_path: Optional[str] = typer.Option(None, "--db-path", "-d", help="Path to SQLite database file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
):
    """Lists registered worker processes and their heartbeat statuses."""
    try:
        settings = get_settings(db_path)
        db_manager = get_db_manager(settings.db_path)

        service = WorkerService(db_manager)
        workers = service.list_workers(status=status)
        print_worker_table(workers, is_json=json_output)
    except Exception as e:
        print_error(f"Failed to list workers: {e}", is_json=json_output)
