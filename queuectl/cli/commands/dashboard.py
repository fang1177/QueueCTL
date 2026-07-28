"""
QueueCTL CLI Dashboard Command.

Launches the live FastAPI monitoring web dashboard.
"""

from typing import Optional
import typer
import uvicorn
from queuectl.cli.formatter import print_error
from queuectl.config.settings import get_settings


def dashboard_command(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host address for dashboard server"),
    port: int = typer.Option(8000, "--port", "-p", help="Port for dashboard server"),
    db_path: Optional[str] = typer.Option(None, "--db-path", "-d", help="Path to SQLite database file"),
):
    """Launches the minimal FastAPI web dashboard for real-time monitoring."""
    try:
        import os
        # Support cloud environment variables (e.g. Render, Heroku)
        env_port = os.getenv("PORT")
        if env_port and port == 8000:
            port = int(env_port)
        if env_port and host == "127.0.0.1":
            host = "0.0.0.0"

        settings = get_settings(db_path)
        os.environ["QUEUECTL_DB_PATH"] = settings.db_path

        print(f"Starting QueueCTL Live Dashboard on http://{host}:{port}")
        uvicorn.run("queuectl.web.app:app", host=host, port=port, log_level="info")
    except Exception as e:
        print_error(f"Failed to start dashboard: {e}")
