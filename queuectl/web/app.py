"""
QueueCTL FastAPI Web Dashboard Module.

Provides live REST API endpoints and a single-page web UI displaying
real-time workers, jobs, queue metrics, and execution logs.
"""

import os
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

from queuectl.config.settings import get_settings
from queuectl.database.connection import get_db_manager
from queuectl.services.metrics_service import MetricsService
from queuectl.services.queue_service import QueueService
from queuectl.services.worker_service import WorkerService

app = FastAPI(
    title="QueueCTL Dashboard",
    description="Real-time background job queue monitoring dashboard.",
    version="1.0.0",
)


def _get_db():
    db_path = os.getenv("QUEUECTL_DB_PATH")
    settings = get_settings(db_path)
    return get_db_manager(settings.db_path)


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


@app.get("/", response_class=HTMLResponse)
def get_dashboard_ui():
    """Renders single-page HTML dashboard with live auto-refresh."""
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
            
            .grid-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
            .stat-card {
                background: var(--card-bg);
                backdrop-filter: blur(12px);
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 1.25rem;
                text-align: center;
            }
            .stat-value { font-size: 2rem; font-weight: 700; margin-top: 0.2rem; }
            .stat-label { color: var(--text-muted); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }

            .section-grid { display: grid; grid-template-columns: 1fr; gap: 2rem; }
            .card {
                background: var(--card-bg);
                backdrop-filter: blur(12px);
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 1.5rem;
            }
            .card-title { font-size: 1.2rem; font-weight: 600; margin-bottom: 1rem; color: var(--accent-blue); }

            table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.9rem; }
            th { padding: 0.75rem; color: var(--text-muted); border-bottom: 1px solid var(--border-color); font-weight: 600; }
            td { padding: 0.75rem; border-bottom: 1px solid var(--border-color); }
            tr:hover { background: rgba(255, 255, 255, 0.03); }

            .status-tag { padding: 0.2rem 0.6rem; border-radius: 4px; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; }
            .status-pending { background: rgba(250, 204, 21, 0.2); color: var(--accent-yellow); }
            .status-processing { background: rgba(56, 189, 248, 0.2); color: var(--accent-blue); }
            .status-completed { background: rgba(74, 222, 128, 0.2); color: var(--accent-green); }
            .status-failed, .status-dead { background: rgba(248, 113, 113, 0.2); color: var(--accent-red); }
            .status-active { background: rgba(74, 222, 128, 0.2); color: var(--accent-green); }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>⚡ QueueCTL Live Dashboard</h1>
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

        <div class="section-grid">
            <div class="card">
                <div class="card-title">👷 Registered Workers</div>
                <table>
                    <thead>
                        <tr><th>Worker ID</th><th>PID</th><th>Status</th><th>Hostname</th><th>Last Heartbeat</th><th>Jobs (S/F)</th></tr>
                    </thead>
                    <tbody id="workers-tbody"><tr><td colspan="6" style="text-align:center;">Loading workers...</td></tr></tbody>
                </table>
            </div>

            <div class="card">
                <div class="card-title">📋 Recent Jobs</div>
                <table>
                    <thead>
                        <tr><th>ID</th><th>Name</th><th>Command</th><th>State</th><th>Attempts</th><th>Worker ID</th></tr>
                    </thead>
                    <tbody id="jobs-tbody"><tr><td colspan="6" style="text-align:center;">Loading jobs...</td></tr></tbody>
                </table>
            </div>
        </div>

        <script>
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
