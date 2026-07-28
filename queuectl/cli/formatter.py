"""
QueueCTL Output Formatter Module.

Formats output for Rich console CLI tables and strict JSON format when requested.
"""

import json
import sys
from typing import Any, Dict, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def print_json_output(data: Any):
    """Outputs pure, valid JSON string without color codes or extra stdout noise."""
    print(json.dumps(data, indent=2, default=str))


def print_success(message: str, is_json: bool = False, json_data: Optional[Dict[str, Any]] = None):
    """Prints success message or JSON payload."""
    if is_json:
        payload = json_data if json_data is not None else {"status": "success", "message": message}
        print_json_output(payload)
    else:
        console.print(f"[bold green][OK] {message}[/bold green]")


def print_error(message: str, is_json: bool = False, exit_code: int = 1):
    """Prints error message or JSON payload and exits cleanly."""
    if is_json:
        print_json_output({"status": "error", "error": message, "exit_code": exit_code})
    else:
        console.print(f"[bold red][ERROR] {message}[/bold red]", file=sys.stderr)
    sys.exit(exit_code)


def print_job_table(jobs: List[Dict[str, Any]], title: str = "Jobs", is_json: bool = False):
    """Renders job list as Rich table or JSON."""
    if is_json:
        print_json_output(jobs)
        return

    if not jobs:
        console.print(f"[yellow]No jobs found for {title}.[/yellow]")
        return

    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim", width=12)
    table.add_column("Name", style="bold white")
    table.add_column("Command")
    table.add_column("State", style="bold")
    table.add_column("Priority", justify="right")
    table.add_column("Attempts", justify="right")
    table.add_column("Scheduled At")
    table.add_column("Worker ID", style="dim")

    state_styles = {
        "pending": "yellow",
        "processing": "blue",
        "completed": "green",
        "failed": "bright_red",
        "dead": "bold red",
    }

    for j in jobs:
        state = j.get("state", "pending")
        state_formatted = f"[{state_styles.get(state, 'white')}]{state}[/{state_styles.get(state, 'white')}]"
        
        job_id_short = j['id'][:8] + "..." if len(j['id']) > 8 else j['id']
        scheduled = j.get("scheduled_at") or "-"
        worker = j.get("worker_id") or "-"

        table.add_row(
            job_id_short,
            j["name"],
            j["command"],
            state_formatted,
            str(j.get("priority", 0)),
            f"{j.get('attempts', 0)}/{j.get('max_retries', 3)}",
            scheduled,
            worker,
        )

    console.print(table)


def print_worker_table(workers: List[Dict[str, Any]], is_json: bool = False):
    """Renders worker list as Rich table or JSON."""
    if is_json:
        print_json_output(workers)
        return

    if not workers:
        console.print("[yellow]No active workers registered.[/yellow]")
        return

    table = Table(title="Worker Registry", show_header=True, header_style="bold magenta")
    table.add_column("Worker ID", style="bold white")
    table.add_column("PID", justify="right")
    table.add_column("Status", style="bold")
    table.add_column("Hostname")
    table.add_column("Last Heartbeat")
    table.add_column("Processed/Failed", justify="center")

    status_styles = {
        "active": "green",
        "stopping": "yellow",
        "stopped": "dim",
        "dead": "bold red",
    }

    for w in workers:
        status = w.get("status", "unknown")
        status_formatted = f"[{status_styles.get(status, 'white')}]{status}[/{status_styles.get(status, 'white')}]"
        counts = f"{w.get('jobs_processed', 0)} / {w.get('jobs_failed', 0)}"

        table.add_row(
            w["id"],
            str(w["pid"]),
            status_formatted,
            w["hostname"],
            w.get("last_heartbeat") or "-",
            counts,
        )

    console.print(table)


def print_status_summary(status_data: Dict[str, Any], is_json: bool = False):
    """Renders queue status summary panel or JSON."""
    if is_json:
        print_json_output(status_data)
        return

    jobs = status_data.get("jobs", {})
    workers = status_data.get("workers", {})
    config = status_data.get("config", {})

    console.print(Panel(
        f"[bold white]Total Jobs:[/bold white] {jobs.get('total', 0)}  |  "
        f"[yellow]Pending:[/yellow] {jobs.get('pending', 0)}  |  "
        f"[blue]Processing:[/blue] {jobs.get('processing', 0)}  |  "
        f"[green]Completed:[/green] {jobs.get('completed', 0)}  |  "
        f"[bright_red]Failed:[/bright_red] {jobs.get('failed', 0)}  |  "
        f"[bold red]Dead (DLQ):[/bold red] {jobs.get('dead', 0)}\n\n"
        f"[bold white]Workers:[/bold white] Total: {workers.get('total_registered', 0)} | "
        f"[green]Active: {workers.get('active_count', 0)}[/green] | "
        f"[yellow]Stopping: {workers.get('stopping_count', 0)}[/yellow] | "
        f"[red]Dead: {workers.get('dead_count', 0)}[/red]\n\n"
        f"[bold white]Key Configs:[/bold white] Max Retries: {config.get('max_retries')} | "
        f"Backoff Base: {config.get('backoff_base')} | Heartbeat: {config.get('heartbeat_interval')}s | "
        f"Recovery Timeout: {config.get('recovery_timeout')}s",
        title="[bold cyan]QueueCTL System Status[/bold cyan]",
        border_style="cyan"
    ))
