"""
QueueCTL CLI Main Entrypoint Module.

Registers all Typer command groups and sets up top-level flags.
"""

import typer
from queuectl import __version__
from queuectl.cli.commands.config import config_app
from queuectl.cli.commands.dashboard import dashboard_command
from queuectl.cli.commands.dlq import dlq_app
from queuectl.cli.commands.enqueue import enqueue_command
from queuectl.cli.commands.init import init_command
from queuectl.cli.commands.list_jobs import list_jobs_command
from queuectl.cli.commands.status import status_command
from queuectl.cli.commands.worker import worker_app

app = typer.Typer(
    name="queuectl",
    help="QueueCTL - Production-grade background job queue system CLI",
    add_completion=False,
)

# Register top-level commands
app.command("init")(init_command)
app.command("enqueue")(enqueue_command)
app.command("status")(status_command)
app.command("list")(list_jobs_command)
app.command("dashboard")(dashboard_command)

# Register subcommands
app.add_typer(worker_app, name="worker")
app.add_typer(dlq_app, name="dlq")
app.add_typer(config_app, name="config")


@app.command("version")
def version_command():
    """Displays current QueueCTL version."""
    typer.echo(f"QueueCTL version {__version__}")


if __name__ == "__main__":
    app()
