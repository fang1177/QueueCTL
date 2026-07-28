"""
QueueCTL FastAPI Web Dashboard Module.

Provides live REST API endpoints, a background worker thread, and a single-page
web UI with interactive job enqueue form displaying real-time workers, jobs,
queue metrics, and execution logs.
"""

import os
import threading
import time
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from queuectl.config.settings import get_settings
from queuectl.database.connection import get_db_manager
from queuectl.models.job import JobCreate
from queuectl.services.metrics_service import MetricsService
from queuectl.services.queue_service import QueueService
from queuectl.services.worker_service import WorkerService

app = FastAPI(
    title="QueueCTL Dashboard",
    description="Real-time background job queue monitoring dashboard.",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Background Worker Thread (runs inside the web process on Render)
# ---------------------------------------------------------------------------
_worker_thread: Optional[threading.Thread] = None
_worker_running = False


def _background_worker_loop():
    """Lightweight in-process worker that claims and executes jobs."""
    global _worker_running
    from queuectl.core.executor import CommandExecutor
    from queuectl.models.enums import JobState
    from queuectl.repositories.job_repository import JobRepository
    from queuectl.repositories.worker_repository import WorkerRepository
    from queuectl.utils.logger import get_logger
    import socket

    logger = get_logger("queuectl.web-worker")
    db_manager = _get_db()
    worker_id = f"web-worker-{socket.gethostname()}-{os.getpid()}"

    # Register worker
    with db_manager.session() as session:
        repo = WorkerRepository(session)
        repo.register(worker_id, os.getpid(), socket.gethostname())

    logger.info(f"Background web worker '{worker_id}' started.")

    while _worker_running:
        try:
            # Heartbeat
            with db_manager.session() as session:
                WorkerRepository(session).update_heartbeat(worker_id)

            # Claim job
            job = None
            with db_manager.session() as session:
                job = JobRepository(session).claim_next_job(worker_id)

            if job:
                logger.info(f"Web worker claimed job '{job.id}' ('{job.name}')")
                exec_result = CommandExecutor.execute(job.command, timeout_seconds=job.timeout)

                with db_manager.session() as session:
                    job_repo = JobRepository(session)
                    worker_repo = WorkerRepository(session)

                    if exec_result["exit_code"] == 0:
                        job_repo.mark_completed(job.id, output=exec_result["stdout"])
                        job_repo.log_execution(
                            job_id=job.id, worker_id=worker_id,
                            attempt=job.attempts + 1, status=JobState.COMPLETED.value,
                            exit_code=0, stdout=exec_result["stdout"],
                            stderr=exec_result["stderr"], duration_ms=exec_result["duration_ms"],
                        )
                        worker_repo.increment_counters(worker_id, success=True)
                    else:
                        updated = job_repo.mark_failed(job.id, error_message=exec_result["error_message"], output=exec_result["stdout"])
                        job_repo.log_execution(
                            job_id=job.id, worker_id=worker_id,
                            attempt=job.attempts, status=updated.state,
                            exit_code=exec_result["exit_code"], stdout=exec_result["stdout"],
                            stderr=exec_result["stderr"], error_message=exec_result["error_message"],
                            duration_ms=exec_result["duration_ms"],
                        )
                        worker_repo.increment_counters(worker_id, success=False)
            else:
                time.sleep(2)
        except Exception as e:
            logger.error(f"Web worker error: {e}")
            time.sleep(3)

    # Cleanup
    try:
        from queuectl.models.enums import WorkerStatus
        with db_manager.session() as session:
            WorkerRepository(session).set_status(worker_id, WorkerStatus.STOPPED)
    except Exception:
        pass


@app.on_event("startup")
def start_background_worker():
    """Start the background worker thread when the web app boots."""
    global _worker_thread, _worker_running
    _worker_running = True
    _worker_thread = threading.Thread(target=_background_worker_loop, daemon=True, name="web-worker")
    _worker_thread.start()


@app.on_event("shutdown")
def stop_background_worker():
    """Stop the background worker thread."""
    global _worker_running
    _worker_running = False


# ---------------------------------------------------------------------------
# DB Helper
# ---------------------------------------------------------------------------
def _get_db():
    db_path = os.getenv("QUEUECTL_DB_PATH")
    settings = get_settings(db_path)
    return get_db_manager(settings.db_path)


# ---------------------------------------------------------------------------
# Enqueue API Model
# ---------------------------------------------------------------------------
class EnqueueRequest(BaseModel):
    name: str
    command: str
    priority: int = 0
    max_retries: int = 3
    timeout: int = 60
    delay_seconds: int = 0


# ---------------------------------------------------------------------------
# REST API Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/status")
def get_status():
    """Returns complete system metrics overview."""
    db_manager = _get_db()
    metrics = MetricsService(db_manager)
    return metrics.get_system_status()


@app.get("/api/jobs")
def get_jobs(state: Optional[str] = None, limit: int = Query(50, ge=1, le=200)):
    """Returns list of jobs filtered by state."""
    db_manager = _get_db()
    service = QueueService(db_manager)
    return service.list_jobs(state=state, limit=limit)


@app.get("/api/workers")
def get_workers():
    """Returns list of registered workers."""
    db_manager = _get_db()
    service = WorkerService(db_manager)
    return service.list_workers()


@app.post("/api/enqueue")
def enqueue_job(req: EnqueueRequest):
    """Enqueue a new job via the web dashboard API."""
    db_manager = _get_db()
    service = QueueService(db_manager)
    payload = JobCreate(
        name=req.name,
        command=req.command,
        priority=req.priority,
        max_retries=req.max_retries,
        timeout=req.timeout,
        delay_seconds=req.delay_seconds,
    )
    result = service.enqueue(payload)
    return result


# ---------------------------------------------------------------------------
# Dashboard HTML UI
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def get_dashboard_ui():
    """Renders single-page HTML dashboard with live auto-refresh and enqueue form."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>QueueCTL Live Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-color: #0f172a;
                --card-bg: rgba(30, 41, 59, 0.7);
                --text-main: #f8fafc;
                --text-muted: #94a3b8;
                --accent-blue: #38bdf8;
                --accent-green: #4ade80;
                --accent-yellow: #facc15;
                --accent-red: #f87171;
                --accent-purple: #a78bfa;
                --border-color: rgba(255, 255, 255, 0.1);
            }
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body {
                font-family: 'Inter', sans-serif;
                background-color: var(--bg-color);
                color: var(--text-main);
                padding: 2rem;
                line-height: 1.5;
            }
            .header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 2rem;
                padding-bottom: 1rem;
                border-bottom: 1px solid var(--border-color);
            }
            .header h1 { font-size: 1.8rem; font-weight: 700; background: linear-gradient(135deg, #38bdf8, #818cf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
            .badge-live { display: flex; align-items: center; gap: 0.5rem; background: rgba(74, 222, 128, 0.15); color: var(--accent-green); padding: 0.3rem 0.8rem; border-radius: 20px; font-size: 0.85rem; font-weight: 600; }
            .pulse { width: 8px; height: 8px; background: var(--accent-green); border-radius: 50%; box-shadow: 0 0 8px var(--accent-green); animation: blink 1.5s infinite; }
            @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

            .grid-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
            .stat-card {
                background: var(--card-bg);
                backdrop-filter: blur(12px);
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 1.25rem;
                text-align: center;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            .stat-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }
            .stat-value { font-size: 2rem; font-weight: 700; margin-top: 0.2rem; }
            .stat-label { color: var(--text-muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }

            .section-grid { display: grid; grid-template-columns: 1fr; gap: 2rem; }
            .card {
                background: var(--card-bg);
                backdrop-filter: blur(12px);
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 1.5rem;
            }
            .card-title { font-size: 1.15rem; font-weight: 600; margin-bottom: 1rem; color: var(--accent-blue); }

            table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.85rem; }
            th { padding: 0.7rem; color: var(--text-muted); border-bottom: 1px solid var(--border-color); font-weight: 600; }
            td { padding: 0.7rem; border-bottom: 1px solid var(--border-color); }
            tr:hover { background: rgba(255, 255, 255, 0.03); }

            .status-tag { padding: 0.2rem 0.6rem; border-radius: 4px; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; }
            .status-pending { background: rgba(250, 204, 21, 0.2); color: var(--accent-yellow); }
            .status-processing { background: rgba(56, 189, 248, 0.2); color: var(--accent-blue); }
            .status-completed { background: rgba(74, 222, 128, 0.2); color: var(--accent-green); }
            .status-failed, .status-dead { background: rgba(248, 113, 113, 0.2); color: var(--accent-red); }
            .status-active { background: rgba(74, 222, 128, 0.2); color: var(--accent-green); }

            /* Enqueue Form */
            .enqueue-form {
                display: grid;
                grid-template-columns: 1fr 2fr;
                gap: 0.75rem;
                align-items: center;
            }
            .enqueue-form label {
                font-size: 0.85rem;
                color: var(--text-muted);
                font-weight: 600;
                text-align: right;
                padding-right: 0.75rem;
            }
            .enqueue-form input, .enqueue-form select {
                background: rgba(15, 23, 42, 0.8);
                border: 1px solid var(--border-color);
                color: var(--text-main);
                padding: 0.6rem 0.8rem;
                border-radius: 8px;
                font-family: 'Inter', sans-serif;
                font-size: 0.85rem;
                outline: none;
                transition: border-color 0.2s;
            }
            .enqueue-form input:focus {
                border-color: var(--accent-blue);
                box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.15);
            }
            .form-row-full {
                grid-column: 1 / -1;
                display: flex;
                gap: 0.75rem;
                justify-content: flex-end;
                margin-top: 0.5rem;
            }
            .btn-enqueue {
                background: linear-gradient(135deg, #38bdf8, #818cf8);
                color: #fff;
                border: none;
                padding: 0.65rem 1.5rem;
                border-radius: 8px;
                font-size: 0.9rem;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.15s, box-shadow 0.2s;
            }
            .btn-enqueue:hover { transform: scale(1.03); box-shadow: 0 4px 16px rgba(56, 189, 248, 0.35); }
            .btn-enqueue:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
            .form-status {
                font-size: 0.85rem;
                padding: 0.5rem 0;
                min-height: 1.5rem;
            }
            .form-status.success { color: var(--accent-green); }
            .form-status.error { color: var(--accent-red); }

            .inline-fields {
                display: flex;
                gap: 1rem;
            }
            .inline-field { display: flex; align-items: center; gap: 0.4rem; }
            .inline-field label { text-align: left; padding-right: 0; font-size: 0.8rem; }
            .inline-field input { width: 70px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>QueueCTL Live Dashboard</h1>
            <div class="badge-live"><div class="pulse"></div> LIVE POLLING</div>
        </div>

        <div class="grid-stats">
            <div class="stat-card"><div class="stat-label">Total Jobs</div><div class="stat-value" id="stat-total">0</div></div>
            <div class="stat-card"><div class="stat-label">Pending</div><div class="stat-value" style="color: var(--accent-yellow)" id="stat-pending">0</div></div>
            <div class="stat-card"><div class="stat-label">Processing</div><div class="stat-value" style="color: var(--accent-blue)" id="stat-processing">0</div></div>
            <div class="stat-card"><div class="stat-label">Completed</div><div class="stat-value" style="color: var(--accent-green)" id="stat-completed">0</div></div>
            <div class="stat-card"><div class="stat-label">Dead (DLQ)</div><div class="stat-value" style="color: var(--accent-red)" id="stat-dead">0</div></div>
            <div class="stat-card"><div class="stat-label">Active Workers</div><div class="stat-value" style="color: var(--accent-green)" id="stat-workers">0</div></div>
        </div>

        <!-- Enqueue Job Form -->
        <div class="section-grid" style="margin-bottom: 2rem;">
            <div class="card">
                <div class="card-title" style="color: var(--accent-purple);">Enqueue New Job</div>
                <form id="enqueue-form" class="enqueue-form" onsubmit="return enqueueJob(event)">
                    <label for="job-name">Job Name</label>
                    <input type="text" id="job-name" placeholder="e.g. Backup Task" required />

                    <label for="job-command">Command</label>
                    <input type="text" id="job-command" placeholder='e.g. echo "Hello World"' required />

                    <label>Options</label>
                    <div class="inline-fields">
                        <div class="inline-field">
                            <label for="job-priority">Priority</label>
                            <input type="number" id="job-priority" value="0" min="0" max="100" />
                        </div>
                        <div class="inline-field">
                            <label for="job-retries">Retries</label>
                            <input type="number" id="job-retries" value="3" min="0" max="20" />
                        </div>
                        <div class="inline-field">
                            <label for="job-timeout">Timeout(s)</label>
                            <input type="number" id="job-timeout" value="60" min="5" max="600" />
                        </div>
                    </div>

                    <div class="form-row-full">
                        <div class="form-status" id="form-status"></div>
                        <button type="submit" class="btn-enqueue" id="btn-submit">Enqueue Job</button>
                    </div>
                </form>
            </div>
        </div>

        <div class="section-grid">
            <div class="card">
                <div class="card-title">Registered Workers</div>
                <table>
                    <thead>
                        <tr><th>Worker ID</th><th>PID</th><th>Status</th><th>Hostname</th><th>Last Heartbeat</th><th>Jobs (S/F)</th></tr>
                    </thead>
                    <tbody id="workers-tbody"><tr><td colspan="6" style="text-align:center;">Loading workers...</td></tr></tbody>
                </table>
            </div>

            <div class="card">
                <div class="card-title">Recent Jobs</div>
                <table>
                    <thead>
                        <tr><th>ID</th><th>Name</th><th>Command</th><th>State</th><th>Attempts</th><th>Worker ID</th></tr>
                    </thead>
                    <tbody id="jobs-tbody"><tr><td colspan="6" style="text-align:center;">Loading jobs...</td></tr></tbody>
                </table>
            </div>
        </div>

        <script>
            async function enqueueJob(e) {
                e.preventDefault();
                const btn = document.getElementById('btn-submit');
                const status = document.getElementById('form-status');
                btn.disabled = true;
                status.className = 'form-status';
                status.innerText = 'Enqueueing...';

                try {
                    const body = {
                        name: document.getElementById('job-name').value,
                        command: document.getElementById('job-command').value,
                        priority: parseInt(document.getElementById('job-priority').value) || 0,
                        max_retries: parseInt(document.getElementById('job-retries').value) || 3,
                        timeout: parseInt(document.getElementById('job-timeout').value) || 60,
                        delay_seconds: 0,
                    };
                    const res = await fetch('/api/enqueue', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(body),
                    });
                    const data = await res.json();
                    if (res.ok) {
                        status.className = 'form-status success';
                        status.innerText = 'Job enqueued: ' + data.id.substring(0, 8) + '...';
                        document.getElementById('job-name').value = '';
                        document.getElementById('job-command').value = '';
                        setTimeout(fetchData, 500);
                    } else {
                        status.className = 'form-status error';
                        status.innerText = 'Error: ' + (data.detail || JSON.stringify(data));
                    }
                } catch(err) {
                    status.className = 'form-status error';
                    status.innerText = 'Network error: ' + err.message;
                }
                btn.disabled = false;
            }

            async function fetchData() {
                try {
                    const [resStatus, resWorkers, resJobs] = await Promise.all([
                        fetch('/api/status').then(r => r.json()),
                        fetch('/api/workers').then(r => r.json()),
                        fetch('/api/jobs?limit=20').then(r => r.json())
                    ]);

                    const j = resStatus.jobs || {};
                    document.getElementById('stat-total').innerText = j.total || 0;
                    document.getElementById('stat-pending').innerText = j.pending || 0;
                    document.getElementById('stat-processing').innerText = j.processing || 0;
                    document.getElementById('stat-completed').innerText = j.completed || 0;
                    document.getElementById('stat-dead').innerText = j.dead || 0;
                    document.getElementById('stat-workers').innerText = resStatus.workers.active_count || 0;

                    // Render Workers Table
                    const wTbody = document.getElementById('workers-tbody');
                    if(resWorkers.length === 0) {
                        wTbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">No active workers registered</td></tr>';
                    } else {
                        wTbody.innerHTML = resWorkers.map(w => `
                            <tr>
                                <td><b>${w.id}</b></td>
                                <td>${w.pid}</td>
                                <td><span class="status-tag status-${w.status}">${w.status}</span></td>
                                <td>${w.hostname}</td>
                                <td>${w.last_heartbeat ? new Date(w.last_heartbeat).toLocaleTimeString() : '-'}</td>
                                <td>${w.jobs_processed} / ${w.jobs_failed}</td>
                            </tr>
                        `).join('');
                    }

                    // Render Jobs Table
                    const jTbody = document.getElementById('jobs-tbody');
                    if(resJobs.length === 0) {
                        jTbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">No jobs in queue</td></tr>';
                    } else {
                        jTbody.innerHTML = resJobs.map(job => `
                            <tr>
                                <td style="font-family: monospace;">${job.id.substring(0,8)}...</td>
                                <td><b>${job.name}</b></td>
                                <td style="font-family: monospace;">${job.command}</td>
                                <td><span class="status-tag status-${job.state}">${job.state}</span></td>
                                <td>${job.attempts} / ${job.max_retries}</td>
                                <td>${job.worker_id || '-'}</td>
                            </tr>
                        `).join('');
                    }
                } catch(err) {
                    console.error('Error fetching dashboard metrics:', err);
                }
            }

            fetchData();
            setInterval(fetchData, 3000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
