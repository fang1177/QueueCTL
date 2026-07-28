"""
QueueCTL CLI Status Command.

Displays comprehensive system health, queue statistics, and worker counts.
"""

from typing import Optional
import typer
from queuectl.cli.formatter import print_error, print_status_summary
from queuectl.config.settings import get_settings
from queuectl.database.connection import get_db_manager
from queuectl.services.metrics_service import MetricsService


def status_command(
    db_path: Optional[str] = typer.Option(None, "--db-path", "-d", help="Path to SQLite database file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
):
    """Displays current queue statistics, job counts, active workers, and settings."""
    try:
        settings = get_settings(db_path)
        db_manager = get_db_manager(settings.db_path)
        service = MetricsService(db_manager)

        status_data = service.get_system_status()
        print_status_summary(status_data, is_json=json_output)
    except Exception as e:
        print_error(f"Failed to retrieve system status: {e}", is_json=json_output)
