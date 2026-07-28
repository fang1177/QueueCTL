"""
QueueCTL CLI Init Command.

Initializes database schema and default configuration.
"""

from typing import Optional
import typer
from queuectl.cli.formatter import print_error, print_success
from queuectl.database.migrations import init_db


def init_command(
    db_path: Optional[str] = typer.Option(None, "--db-path", "-d", help="Path to SQLite database file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
):
    """Initializes the QueueCTL database tables and configuration."""
    try:
        path = init_db(db_path)
        print_success(
            f"Database initialized successfully at: {path}",
            is_json=json_output,
            json_data={"status": "success", "db_path": path}
        )
    except Exception as e:
        print_error(f"Failed to initialize database: {e}", is_json=json_output)
