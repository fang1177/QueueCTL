# ⚡ QueueCTL - Production-Grade Background Job Queue System

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Database](https://img.shields.io/badge/database-SQLite--WAL-green.svg)](https://www.sqlite.org/)
[![Architecture](https://img.shields.io/badge/architecture-Clean%20Architecture-orange.svg)](ARCHITECTURE.md)
[![Tests](https://img.shields.io/badge/tests-23%20passed-brightgreen.svg)](tests/)

**QueueCTL** is a CLI-based background job queue system built in Python 3.11+ using SQLite with Write-Ahead Logging (WAL), SQLAlchemy 2.0, Typer, and Pydantic. It provides guaranteed **Exactly-Once Job Execution**, **Atomic Job Claiming**, **Automatic Crash Recovery (<60s)**, **Exponential Backoff Retries**, **Dead Letter Queue (DLQ)**, and a **FastAPI Monitoring Dashboard**.

---

## 📋 Table of Contents
1. [System Features & Highlights](#-system-features--highlights)
2. [Prerequisites](#-prerequisites)
3. [Step-by-Step Installation](#-step-by-step-installation)
4. [Complete Command Execution Guide](#-complete-command-execution-guide)
   - [Initializing Database](#1-initialize-database)
   - [Enqueueing Jobs](#2-enqueueing-jobs)
   - [Running Worker Processes](#3-running-worker-processes)
   - [Checking Queue Status](#4-checking-queue-status)
   - [Listing Queued Jobs](#5-listing-queued-jobs)
   - [Dead Letter Queue (DLQ) Management](#6-dead-letter-queue-dlq-management)
   - [Dynamic Configuration](#7-dynamic-configuration)
   - [Cross-Terminal Worker Stop](#8-cross-terminal-worker-stop)
   - [FastAPI Web Dashboard](#9-fastapi-web-dashboard)
5. [Automated Showcase & Crash Recovery Scripts](#-automated-showcase--crash-recovery-scripts)
6. [Running the Test Suite](#-running-the-test-suite)
7. [System Architecture & File Structure](#-system-architecture--file-structure)
8. [Documentation Links](#-documentation-links)

---

## 🌟 System Features & Highlights

- **Atomic Job Claiming**: Multiple worker processes running in parallel across terminals **NEVER** execute the same job (`BEGIN IMMEDIATE` + `UPDATE ... RETURNING`).
- **Automatic Crash Recovery (<60s)**: If a worker process receives `SIGKILL` (`kill -9`), orphaned jobs are automatically reclaimed in under 40 seconds.
- **Exponential Backoff Retries**: Failed jobs retry automatically with exponential delay ($\text{delay} = \text{base}^{\text{attempts}}$ seconds).
- **Dead Letter Queue (DLQ)**: Failed jobs exceeding `max_retries` transition to DLQ state for operator inspection and re-enqueueing.
- **Cross-Terminal Control**: Stop workers across terminals via database registry signaling.
- **Strict JSON Output Support**: Every CLI command supports `--json` for scripting and CI/CD integration.
- **FastAPI Web Dashboard**: Live real-time single-page UI displaying active workers, job status breakdown, and execution logs.

---

## 🔧 Prerequisites

- **Python**: Version 3.11 or higher
- **Git**: Installed on your system
- **Operating System**: Windows (PowerShell/CMD), macOS, or Linux

---

## 📥 Step-by-Step Installation

### Step 1: Clone the Repository
Open your terminal and clone the repository:
```bash
git clone https://github.com/fang1177/QueueCTL.git
cd QueueCTL
```

### Step 2: Install Package in Editable Mode
Install QueueCTL and its required dependencies (`sqlalchemy`, `typer`, `pydantic`, `fastapi`, `uvicorn`, `rich`, `psutil`, `pyyaml`, `pytest`):
```bash
python -m pip install -e .
```

### Step 3: Initialize the Database
Run the initial database setup to create SQLite tables and default settings:
```bash
queuectl init
```
*Output:*
```text
[OK] Database initialized successfully at: C:\Users\<Username>\.queuectl\queuectl.db
```

---

## 🚀 Complete Command Execution Guide

> 💡 **Shell Quoting Tip**:
> - **PowerShell (Windows)**: Use single quotes `'...'` around `--command` arguments to prevent PowerShell from parsing nested quotes or semicolons.
> - **Bash (Linux/macOS)**: Standard double or single quotes work seamlessly.

---

### 1. Initialize Database
Re-initialize database or specify a custom DB path:
```bash
# Default initialization
queuectl init

# Custom DB path
queuectl init --db-path ./my_queue.db

# Output as JSON
queuectl init --json
```

---

### 2. Enqueueing Jobs
Enqueue shell commands into the queue with custom priority, retries, exponential backoff, and execution delay.

#### PowerShell (Windows):
```powershell
# Basic Job
queuectl enqueue --name "Hello Task" --command "echo Hello QueueCTL"

# High Priority Job (Priority 10, Max Retries 5)
queuectl enqueue --name "Critical Export" --command 'python -c "print(\"Export completed!\")"' --priority 10 --max-retries 5

# Delayed Scheduled Job (Runs after 10 seconds)
queuectl enqueue --name "Delayed Report" --command "echo Delayed task finished" --delay 10

# Failing Job (Fails and retries twice -> moves to DLQ)
queuectl enqueue --name "Failing Job" --command 'python -c "import sys; sys.exit(1)"' --max-retries 2

# Output job details as JSON
queuectl enqueue --name "JSON Job" --command "echo JSON output" --json
```

#### Bash (Linux/macOS):
```bash
# Basic Job
queuectl enqueue --name "Hello Task" --command "echo 'Hello QueueCTL'"

# High Priority Job
queuectl enqueue --name "Critical Export" --command "python -c 'print(\"Export completed!\")'" --priority 10 --max-retries 5

# Delayed Scheduled Job
queuectl enqueue --name "Delayed Report" --command "echo 'Delayed task finished'" --delay 10

# Failing Job
queuectl enqueue --name "Failing Job" --command "python -c 'import sys; sys.exit(1)'" --max-retries 2
```

---

### 3. Running Worker Processes
Workers poll the queue, claim jobs atomically, and execute shell commands in foreground terminals.

```bash
# Start worker process
queuectl worker start

# Start worker with custom ID
queuectl worker start --id worker-node-01
```

> 💡 **Multi-Worker Execution**: Open **2 or 3 separate terminal tabs**, navigate to the project directory, and run `queuectl worker start` in each terminal to observe parallel job processing!

---

### 4. Checking Queue Status
Display real-time system metrics, total jobs, pending/processing/completed/dead counts, and registered workers:

```bash
# Formatted Rich panel output
queuectl status

# Raw JSON format
queuectl status --json
```

---

### 5. Listing Queued Jobs
Query jobs in the database with optional state filtering and pagination:

```bash
# List all jobs
queuectl list

# Filter by state (pending, processing, completed, failed, dead)
queuectl list --state pending
queuectl list --state completed
queuectl list --state dead

# Pagination and JSON output
queuectl list --state completed --limit 10 --json
```

---

### 6. Dead Letter Queue (DLQ) Management
Inspect jobs that failed all retry attempts and re-enqueue them for execution:

```bash
# 1. List dead jobs in the DLQ
queuectl dlq list

# 2. Re-enqueue a dead job (resets attempts counter to 0 and state back to pending)
queuectl dlq retry b9ef3925-8452-481e-b517-a111df3008aa
```

---

### 7. Dynamic Configuration
Update system parameters at runtime without restarting active worker processes:

```bash
# Update maximum retries
queuectl config set max_retries 5

# Update exponential backoff base multiplier (delay = base ^ attempts)
queuectl config set backoff_base 3.0

# Update worker heartbeat interval (seconds)
queuectl config set heartbeat_interval 3.0

# Display active runtime configurations
queuectl config show
```

---

### 8. Cross-Terminal Worker Stop
Gracefully request active worker processes to terminate cleanly from any terminal tab:

```bash
# Stop a specific worker process
queuectl worker stop worker-node-01

# Stop all active workers across terminals
queuectl worker stop
```

---

### 9. FastAPI Web Dashboard
Launch the live, real-time single-page web monitoring UI:

```bash
queuectl dashboard --port 8000
```
> 🌐 Open your web browser at **[http://127.0.0.1:8000](http://127.0.0.1:8000)** to view live auto-refreshing worker statuses, queue metrics, and job execution logs.

---

## 🧪 Automated Showcase & Crash Recovery Scripts

Run pre-built demonstration scripts to see QueueCTL's features in action:

### 1. Automated End-to-End Showcase Demo
Initializes a temporary database, enqueues sample jobs (successful, failing, delayed), launches a worker process, and displays live metrics:
```bash
python scripts/demo.py
```

### 2. SIGKILL Worker Crash Simulator
Simulates a `SIGKILL` (`kill -9`) worker process crash to prove automatic job recovery under 60 seconds:
```bash
python scripts/simulate_crash.py
```

---

## 🔬 Running the Test Suite

Run the full pytest suite (23 unit and parallel process concurrency tests):
```bash
pytest
```
*Output:*
```text
============================= 23 passed in 2.17s ==============================
```

---

## 🏛️ System Architecture & File Structure

```
QueueCTL/
├── cli/                 # Typer CLI Commands & Rich/JSON Formatters
├── core/                # Subprocess Executor, Signal Handlers, Backoff Math, Exceptions
├── config/              # Dynamic Configuration Manager & Defaults
├── database/            # Database Engine (SQLite WAL) & Migrations
├── models/              # SQLAlchemy 2.0 ORM Models & Pydantic Schemas
├── repositories/        # Repository Pattern Data Access Layer
├── services/            # Core Domain Services (Queue, Worker, Recovery, Metrics)
├── workers/             # Worker Event Loop & Heartbeat Daemon Thread
├── web/                 # FastAPI Live Monitoring Web Dashboard
├── tests/               # Pytest Suite (23 Unit & Concurrency Tests)
├── scripts/             # Automated Demo & SIGKILL Crash Recovery Scripts
├── README.md            # Installation & Usage Guide
├── DECISIONS.md         # In-Depth Engineering Rationale & Tradeoffs
├── ARCHITECTURE.md      # Mermaid Architectural Diagrams
├── FLOW.md              # State Machine & Data Flow Specs
└── INTERVIEW.md         # 100 Technical Interview Questions & Defensible Answers
```

---

## 📄 Documentation Links
- 📐 **[ARCHITECTURE.md](ARCHITECTURE.md)** - Component, Sequence, State, and ERD Diagrams.
- ⚙️ **[DECISIONS.md](DECISIONS.md)** - Deep Architectural Rationale & Tradeoffs.
- 🔄 **[FLOW.md](FLOW.md)** - Data Flow Specifications.
- 🎯 **[INTERVIEW.md](INTERVIEW.md)** - 100 Technical Interview Questions & Answers.
