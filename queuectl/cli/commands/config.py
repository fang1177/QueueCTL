"""
QueueCTL CLI Configuration Commands Module.

Provides subcommands for viewing and setting runtime configurations.
"""

from typing import Optional
import typer
from queuectl.cli.formatter import print_error, print_json_output, print_success
from queuectl.config.settings import get_settings
from queuectl.database.connection import get_db_manager
from queuectl.services.config_service import ConfigService
from rich.console import Console
from rich.table import Table

config_app = typer.Typer(help="Manage dynamic QueueCTL configuration settings")
console = Console()


@config_app.command("set")
def set_config_command(
    key: str = typer.Argument(..., help="Configuration key (e.g. max_retries, backoff_base, heartbeat_interval, recovery_timeout)"),
    value: str = typer.Argument(..., help="New value for configuration key"),
    db_path: Optional[str] = typer.Option(None, "--db-path", "-d", help="Path to SQLite database file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
):
    """Sets a runtime system configuration key-value pair in SQLite."""
    try:
        settings = get_settings(db_path)
        db_manager = get_db_manager(settings.db_path)
        service = ConfigService(db_manager)

        updated_item = service.set_config(key, value)
        msg = f"Configuration '{key}' updated to '{value}'."
        print_success(msg, is_json=json_output, json_data=updated_item)
    except Exception as e:
        print_error(f"Failed to set config: {e}", is_json=json_output)


@config_app.command("show")
def show_config_command(
    db_path: Optional[str] = typer.Option(None, "--db-path", "-d", help="Path to SQLite database file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output result as JSON"),
):
    """Displays all current system configuration settings."""
    try:
        settings = get_settings(db_path)
        db_manager = get_db_manager(settings.db_path)
        service = ConfigService(db_manager)

        configs = service.get_all_configs()

        if json_output:
            print_json_output(configs)
            return

        table = Table(title="QueueCTL Runtime Configurations", show_header=True, header_style="bold green")
        table.add_column("Key", style="bold white")
        table.add_column("Value", style="cyan")

        for k, v in configs.items():
            table.add_row(k, str(v))

        console.print(table)
    except Exception as e:
        print_error(f"Failed to show config: {e}", is_json=json_output)
