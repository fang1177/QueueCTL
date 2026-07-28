# QueueCTL - Architectural Decisions & Technical Rationale (DECISIONS.md)

This document provides in-depth technical justifications for every architectural and engineering choice in **QueueCTL**. It is designed to defend every line of code during technical code reviews and live architecture interviews.

---

## 1. Why SQLite with Write-Ahead Logging (WAL)?

### Context & Requirements
Background job queue systems require reliable persistence, low setup friction, fast transactional state updates, and crash resiliency across independent processes.

### Decision
We chose **SQLite** configured in **Write-Ahead Logging (WAL) Mode** (`PRAGMA journal_mode=WAL;`) with a **5000ms Busy Timeout** (`PRAGMA busy_timeout=5000;`).

### Justification & Tradeoffs
- **Zero Heavy Infrastructure**: Eliminates complex external daemon requirements (Redis, RabbitMQ, PostgreSQL), making QueueCTL instantly executable on any system without docker or network configuration.
- **Concurrent Readers & Single Writer**: Standard SQLite rollback journals lock the entire database file during writes, blocking readers. WAL mode allows **concurrent reads while a write transaction is executing**, preventing process starvation.
- **Crash Safety**: In WAL mode, committed transactions are appended to the `-wal` file before modifying the main database. In the event of an abrupt process crash or power loss, uncommitted transactions roll back cleanly, preventing database corruption.
- **Tradeoffs**: SQLite write concurrency is serialized to a single writer process at a time. While sufficient for high-throughput single-node processing (thousands of jobs/sec), a distributed multi-node system would require PostgreSQL or Redis.

---

## 2. How Atomic Job Claiming Works (Exactly-Once Semantics)

### The Concurrency Problem
When multiple worker processes run concurrently in separate terminals, they poll the queue simultaneously. Without atomic locking, Process A and Process B might read the exact same `pending` job at the same instant and both execute it, causing **duplicate execution bugs**.

### Solution: Atomic State Transition in SQLite
QueueCTL implements atomic job claiming using an explicit `BEGIN IMMEDIATE` transaction paired with a single atomic SQL `UPDATE ... RETURNING` query in `queuectl/repositories/job_repository.py`:

```python
# Exact Code from queuectl/repositories/job_repository.py (lines 60-95)

def claim_next_job(self, worker_id: str) -> Optional[Job]:
    now = utc_now()
    
    # Step 1: Force SQLite engine to acquire RESERVED write lock immediately
    self.session.execute(text("BEGIN IMMEDIATE"))

    # Step 2: Single atomic statement selecting & locking target job row
    claim_sql = text("""
        UPDATE jobs
        SET state = :processing_state,
            worker_id = :worker_id,
            started_at = :now,
            updated_at = :now
        WHERE id = (
            SELECT id FROM jobs
            WHERE state = :pending_state
              AND (scheduled_at IS NULL OR scheduled_at <= :now)
            ORDER BY priority DESC, created_at ASC
            LIMIT 1
        )
        RETURNING id;
    """)

    result = self.session.execute(
        claim_sql,
        {
            "processing_state": JobState.PROCESSING.value,
            "pending_state": JobState.PENDING.value,
            "worker_id": worker_id,
            "now": now
        }
    ).fetchone()

    if not result:
        return None

    claimed_id = result[0]
    claimed_job = self.session.get(Job, claimed_id)
    if claimed_job:
        self.session.expunge(claimed_job)
    return claimed_job
```

### Why This Guarantees Atomic Claiming (Interview Defense)
1. **Immediate Write Lock**: `BEGIN IMMEDIATE` acquires a reserved write lock on the database before reading rows. No other worker can initiate a write transaction concurrently.
2. **Atomic Subquery Update**: The `UPDATE` statement atomically evaluates the inner `SELECT` subquery and updates the row state from `pending` to `processing` within the write lock.
3. **Zero Race Windows**: If two workers execute `claim_next_job()` simultaneously, SQLite serializes their execution. Worker 1 claims the highest-priority pending job and changes its state to `processing`. When Worker 2's transaction executes, that job is no longer `pending`, so Worker 2 receives the next pending job or `None`.

---

## 3. Crash Recovery Mechanism (<60 Seconds SLA)

### Problem
If a worker process receives `SIGKILL` (`kill -9`) or suffers an unhandled OS segmentation fault, no application code, `try/finally` block, or signal handler executes. The worker process dies instantly, leaving its DB record as `active` and its assigned job stranded in the `processing` state forever.

### QueueCTL Solution
1. **Periodic Heartbeat**: Every active worker process runs a background daemon thread updating `last_heartbeat = NOW()` in the `workers` table every `heartbeat_interval` seconds (default 5.0s).
2. **Heartbeat Silence Detection**: The `CrashRecoveryService` periodically checks for workers whose `last_heartbeat` timestamp is older than `recovery_timeout` (default 30.0s).
3. **Automatic Job Reclaiming**:
   - The crashed worker's database status is updated to `DEAD`.
   - Any job assigned to the dead worker in state `processing` is orphaned.
   - If `attempts < max_retries`, the job's state is reset to `pending`, `worker_id = NULL`, and `scheduled_at = NOW()`.
   - Remaining active workers pick up the reclaimed job immediately. Total recovery duration is **under 35-40 seconds**, well within the 60-second requirement.

---

## 4. Cross-Terminal Worker Stop Design

### Alternative 1 (Rejected): Raw OS Signals Only (`os.kill(pid, SIGINT)`)
- **Drawback**: Fails if workers run in containerized environments, isolated process namespaces, or different user sessions where OS signals cannot cross boundary permissions.

### Alternative 2 (Chosen): Database Signal Flag + Local Signal Fallback
- **Implementation**: When `queuectl worker stop [worker_id]` is run in any terminal, it updates the target worker's database record status to `STOPPING`.
- Each worker's background heartbeat loop checks its database status every tick. When it reads `STOPPING`, it sets the worker's internal graceful shutdown flag.
- Additionally, if the process is running on the local host, `psutil` sends a `SIGINT` signal to accelerate immediate thread unblocking.
- **Benefit**: Robust, works across separate terminal tabs, SSH sessions, and background daemons.

---

## 5. Exponential Backoff & Retry Design

### Formula
$$\text{delay} = \text{backoff\_base}^{\text{attempts}} \text{ seconds}$$

Example with `backoff_base = 2.0`:
- Attempt 1 failure: $2^1 = 2$ seconds delay
- Attempt 2 failure: $2^2 = 4$ seconds delay
- Attempt 3 failure: $2^3 = 8$ seconds delay

### Rationale
Exponential backoff prevents **thundering herd problems** and avoids hammering failing downstream services (e.g. rate-limited external APIs or database reconnects).

---

## 6. Dead Letter Queue (DLQ) & Reset Strategy

### Decision
When a job exceeds `max_retries`, its state transitions to `DEAD` (DLQ). When an operator runs `queuectl dlq retry <job_id>`, QueueCTL resets `attempts = 0` and `state = 'pending'`.

### Justification
Manual DLQ intervention signifies human/operator remediation (e.g. fixing database credentials, deploying code patch, or restoring network routing). Once remediated, the job should receive a fresh allocation of retries rather than failing instantly on attempt $N+1$.

---

## 7. Tradeoffs & Future Scaling Options

| Feature Aspect | Current QueueCTL Design | Future Scale Architecture (100k+ jobs/sec) |
|---|---|---|
| **Database** | SQLite WAL | PostgreSQL with Advisory Locks / Redis |
| **Worker Coordination** | Database Polling (`SELECT ... FOR UPDATE`) | Redis Pub/Sub / RabbitMQ AMQP |
| **Process Model** | `multiprocessing` / Python Subprocess | AsyncIO event loops / Kubernetes Worker pods |
