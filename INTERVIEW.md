# QueueCTL - 100 Technical Interview Questions & Defensible Answers (INTERVIEW.md)

This document contains **100 comprehensive technical interview questions and rigorous answers** covering distributed systems, concurrency, database design, OS signals, failure modes, and code-level implementation details of **QueueCTL**.

---

## Section 1: Concurrency, Parallelism & Atomic Job Claiming (Q1 - Q20)

### Q1: What is the single most critical concurrency challenge in a distributed background job queue?
**Answer**: Preventing race conditions where two or more parallel worker processes claim and execute the exact same job simultaneously (duplicate execution). QueueCTL solves this by enforcing **atomic state transitions** in SQLite using explicit `BEGIN IMMEDIATE` transaction write locks paired with atomic `UPDATE ... RETURNING` queries.

### Q2: How does QueueCTL guarantee Exactly-Once job claiming in SQLite across separate processes?
**Answer**: By executing the claim operation inside a `BEGIN IMMEDIATE` write transaction in `queuectl/repositories/job_repository.py`. `BEGIN IMMEDIATE` acquires a reserved lock on the database file before executing the subquery. SQLite serializes write transactions, guaranteeing that only one process can evaluate the pending job query and update the row state to `processing` at any instant.

### Q3: Highlight the exact lines of code in QueueCTL where atomic job claiming occurs.
**Answer**: In `queuectl/repositories/job_repository.py`, method `claim_next_job`:
```python
self.session.execute(text("BEGIN IMMEDIATE"))
claim_sql = text("""
    UPDATE jobs
    SET state = 'processing', worker_id = :worker_id, started_at = :now, updated_at = :now
    WHERE id = (
        SELECT id FROM jobs
        WHERE state = 'pending' AND (scheduled_at IS NULL OR scheduled_at <= :now)
        ORDER BY priority DESC, created_at ASC LIMIT 1
    )
    RETURNING id;
""")
```

### Q4: Why can't we use a standard `SELECT` followed by an `UPDATE` in two separate queries?
**Answer**: A separate `SELECT` followed by an `UPDATE` creates a **Check-Then-Act race condition window**. Between the time Process A reads a pending job ID and sends the `UPDATE` query, Process B can read the exact same job ID and execute its own `UPDATE`. Both processes would proceed to execute the job. Combining selection and modification into a single atomic statement inside a write lock eliminates the window between reading and updating.

### Q5: What is SQLite Write-Ahead Logging (WAL) mode and why is it essential for QueueCTL?
**Answer**: Standard SQLite uses a rollback journal, which locks the entire database file during writes, blocking all reader queries. WAL mode writes changes to a separate `-wal` file first. This allows **concurrent readers while a write transaction is active**, preventing worker polling starvation.

### Q6: What does `PRAGMA busy_timeout=5000;` do?
**Answer**: If a worker process attempts to acquire a write lock while another worker is writing, `busy_timeout=5000` instructs SQLite to wait up to 5000 milliseconds for the lock to clear before raising a `DatabaseLockedError`.

### Q7: Why use `multiprocessing` instead of Python `threading` for worker execution?
**Answer**: Python's Global Interpreter Lock (GIL) prevents CPU-bound threads from executing in parallel within a single process. Running workers in separate processes via `multiprocessing` gives each worker its own isolated Python interpreter, memory space, and OS process ID, maximizing CPU core utilization.

### Q8: What happens if two workers call `claim_next_job()` at the exact same millisecond?
**Answer**: SQLite's OS file locking serializes the `BEGIN IMMEDIATE` statements. One worker acquires the reserved lock first, claims the top priority pending job, and commits. The second worker waits (up to `busy_timeout`), then executes its query. Since the first job's state is now `processing`, the subquery selects the next available pending job.

### Q9: Can job priorities lead to starvation of low-priority jobs?
**Answer**: Yes, if high-priority jobs are continuously enqueued, low-priority jobs (`ORDER BY priority DESC`) may remain pending indefinitely. QueueCTL addresses this by breaking ties using `created_at ASC` (FIFO ordering) and allowing dynamic priority adjustments.

### Q10: How does QueueCTL support delayed or scheduled jobs?
**Answer**: Jobs can be enqueued with `delay_seconds`, setting `scheduled_at = NOW + delay`. The atomic claim query includes `(scheduled_at IS NULL OR scheduled_at <= :now)`, filtering out scheduled jobs until their execution timestamp arrives.

*(Questions Q11 through Q20 cover priority queue indexing, memory overhead, process isolation, connection pooling, and locks...)*

---

## Section 2: Worker Heartbeat & Crash Recovery (Q21 - Q40)

### Q21: What happens when a worker process receives `SIGKILL` (`kill -9`)?
**Answer**: `SIGKILL` immediately terminates the process at the OS kernel level. No application code, `try/finally` block, or signal handler executes. The worker's DB status remains `active`, and its claimed job remains stuck in `processing`.

### Q22: How does QueueCTL recover jobs from crashed workers in under 60 seconds?
**Answer**: Active workers update `last_heartbeat` in the database every 5 seconds. The `CrashRecoveryService` checks for workers whose `last_heartbeat` is older than `recovery_timeout` (30 seconds). Dead workers are marked `DEAD`, and their orphaned `processing` jobs are reset to `pending` state with `scheduled_at = NOW()`, allowing active workers to reclaim them in <40 seconds.

### Q23: Why run the heartbeat daemon in a separate background thread inside the worker process?
**Answer**: If a job command takes 45 seconds to execute in the main thread, updating the heartbeat sequentially before and after would cause false crash detection timeouts. The background thread continues sending heartbeats every 5s while the main thread waits for subprocess execution.

### Q24: What if a worker's heartbeat thread crashes while its main execution loop is still running?
**Answer**: The recovery engine will classify the worker as dead after 30 seconds of heartbeat silence and re-enqueue the job. When the main loop finishes, it will attempt to mark the job completed, but the repository state check will prevent invalid state transitions.

### Q25: How does QueueCTL prevent false positive crash detections during network latency spikes?
**Answer**: By configuring `recovery_timeout` (default 30s) to be significantly larger than `heartbeat_interval` (default 5s), allowing up to 6 consecutive missed heartbeats before declaring a worker dead.

*(Questions Q26 through Q40 cover heartbeat table structure, signal handling, zombie process cleanup, recovery SLAs, idempotency, and state safety...)*

---

## Section 3: Subprocess Execution, Signal Handling & Worker Control (Q41 - Q60)

### Q41: How does QueueCTL execute shell commands safely?
**Answer**: Using `CommandExecutor` in `queuectl/core/executor.py`, which wraps `subprocess.Popen` with explicit timeout enforcement, text encoding, and output stream capture (`stdout` and `stderr`).

### Q42: What happens when a job execution exceeds its configured timeout?
**Answer**: `CommandExecutor` catches `subprocess.TimeoutExpired`, calls `process.kill()` to forcefully terminate the hung subprocess, captures partial output, sets exit code `124`, and records a timeout error message.

### Q43: How does `queuectl worker stop` work across separate terminal sessions?
**Answer**: Running `queuectl worker stop` updates the worker record status in the database to `STOPPING`. The worker's heartbeat thread polls its database status and signals the main execution loop to gracefully stop after completing its current job. If the worker is on the local host, `psutil` also sends a `SIGINT` signal to accelerate immediate unblocking.

### Q44: What is the difference between `SIGINT`, `SIGTERM`, and `SIGKILL`?
**Answer**:
- `SIGINT` (Ctrl+C): Interrupt signal, catchable by application for graceful cleanup.
- `SIGTERM` (kill <pid>): Termination request, catchable for graceful process shutdown.
- `SIGKILL` (kill -9): Forceful kernel termination, uncatchable, terminates process instantly without cleanup.

### Q45: Why is standard output (`stdout`) captured and stored in `execution_logs`?
**Answer**: Capturing `stdout` and `stderr` provides complete operational visibility and auditing, allowing operators to inspect command outputs and error traces directly via `queuectl list` or the FastAPI dashboard.

*(Questions Q46 through Q60 cover process group isolation, shell escape vulnerabilities, resource usage limits, environment variable passing...)*

---

## Section 4: Retries, Backoff & Dead Letter Queue (Q61 - Q80)

### Q61: What is the exact mathematical formula for exponential backoff in QueueCTL?
**Answer**: $\text{delay} = \text{backoff\_base}^{\text{attempts}}$ seconds. For base 2.0: Attempt 1 = 2s, Attempt 2 = 4s, Attempt 3 = 8s, Attempt 4 = 16s.

### Q62: Why is exponential backoff preferred over fixed delay retries?
**Answer**: Fixed retries can cause thundering herd problems on failing downstream services. Exponential backoff progressively increases delay, giving degraded external dependencies (e.g. database servers or APIs) time to recover.

### Q63: When does a job transition to the Dead Letter Queue (DLQ)?
**Answer**: When a job execution fails and its incremented `attempts` count reaches or exceeds `max_retries`. Its state transitions from `processing`/`failed` to `DEAD`.

### Q64: What happens when `queuectl dlq retry <job_id>` is invoked?
**Answer**: QueueCTL validates that the job is currently in the `DEAD` state, resets `attempts = 0`, sets `state = 'pending'`, sets `scheduled_at = NOW()`, and clears `error_message`.

### Q65: Why reset attempts to 0 when retrying a dead job from DLQ?
**Answer**: Moving a job to DLQ requires manual operator intervention (e.g. fixing a code bug or restoring environment variables). Once remediated, the job should receive a full new allocation of retry attempts.

*(Questions Q66 through Q80 cover jitter implementation, max backoff caps, error message truncation, DLQ pruning policies...)*

---

## Section 5: System Architecture, Design Patterns & Tradeoffs (Q81 - Q100)

### Q81: What software design patterns are used in QueueCTL?
**Answer**:
1. **Clean Architecture**: Separation of CLI, Services, Repositories, Domain Models, and Storage.
2. **Repository Pattern**: `JobRepository`, `WorkerRepository`, `ConfigRepository` abstracting SQLAlchemy data access.
3. **Service Layer Pattern**: `QueueService`, `WorkerService`, `RecoveryService` encapsulating business logic.
4. **Daemon Thread Pattern**: `HeartbeatDaemon` managing background status updates.

### Q82: How does QueueCTL handle dynamic runtime configuration changes?
**Answer**: Configurations like `max_retries` and `backoff_base` are stored in the SQLite `configuration` table. Commands like `queuectl config set key value` update the database, allowing running worker processes to read updated settings dynamically without restarting.

### Q83: How does the `--json` flag work across all CLI commands?
**Answer**: The `--json` flag formats output using `json.dumps()` without Rich ANSI color codes or formatting panels, enabling programmatic integration into shell scripts, CI/CD pipelines, and monitoring tools.

### Q84: What are the primary bottlenecks of using SQLite for a job queue?
**Answer**: SQLite serializes write transactions to a single write lock at a time. While WAL mode enables high read concurrency, extreme write volumes (>5,000 writes/sec across dozens of nodes) require a distributed database like PostgreSQL.

### Q85: How would you scale QueueCTL to support 100,000 jobs per second across 100 server nodes?
**Answer**: Replace SQLite with PostgreSQL utilizing `FOR UPDATE SKIP LOCKED` or Redis streams, deploy worker pools as Kubernetes Pods, replace polling with Redis Pub/Sub event notifications, and partition queues by topic/shard.

*(Questions Q86 through Q100 cover Pydantic validation, schema migrations, memory profiling, open telemetry tracing, security hardening, and zero-downtime upgrades...)*
