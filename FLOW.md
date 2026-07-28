# QueueCTL - Detailed Data Flows & State Machine Specifications (FLOW.md)

This document details the lifecycle data flows, state machine rules, and transition validation constraints in **QueueCTL**.

---

## 1. Job State Machine & Valid Transitions Matrix

A QueueCTL job transitions through 5 immutable states: `pending`, `processing`, `completed`, `failed`, `dead`.

```
                    ┌─────────────┐
                    │   PENDING   │◄──────────────┐ (Manual DLQ Retry)
                    └──────┬──────┘               │
                           │                      │
                   (Atomic │ Claim)               │
                           ▼                      │
                    ┌─────────────┐               │
                    │ PROCESSING  │               │
                    └───┬─────┬───┘               │
                        │     │                   │
             (Exit 0)   │     │ (Exit != 0)       │
         ┌──────────────┘     └──────────────┐    │
         ▼                                   ▼    │
  ┌─────────────┐                     ┌───────────┴─┐
  │  COMPLETED  │                     │   FAILED    │
  └─────────────┘                     └──────┬──────┘
                                             │
                                    (Attempts < Max Retries)
                                             │ [Reschedule Exponential Backoff]
                                             ▼
                                      ┌─────────────┐
                                      │   PENDING   │
                                      └─────────────┘
                                             │
                                    (Attempts >= Max Retries)
                                             ▼
                                      ┌─────────────┐
                                      │    DEAD     │ (Dead Letter Queue)
                                      └─────────────┘
```

### Valid Transition Matrix

| From State | Allowed Target States | Trigger Condition |
|---|---|---|
| **PENDING** | `PROCESSING`, `DEAD` | Atomically claimed by worker OR directly cancelled |
| **PROCESSING** | `COMPLETED`, `FAILED`, `PENDING`, `DEAD` | Exit code 0, non-zero exit code, worker crash recovery reclaim |
| **FAILED** | `PENDING`, `DEAD` | Exponential backoff reschedule OR max retries exceeded |
| **COMPLETED** | *None (Terminal)* | Execution finished successfully |
| **DEAD** | `PENDING` | Manual `queuectl dlq retry` intervention |

---

## 2. End-to-End Data Flow Scenarios

### Scenario A: Successful Job Lifecycle
1. User executes `queuectl enqueue --name "Backup" --command "tar -czf backup.tgz /data"`.
2. `QueueService` validates `JobCreate` schema and creates a record in `jobs` table with `state = 'pending'`.
3. Worker process polls database and calls `JobRepository.claim_next_job(worker_id)`.
4. SQLite executes atomic `BEGIN IMMEDIATE; UPDATE ... RETURNING id;` transaction, transitioning state to `processing` and returning job.
5. Worker updates `HeartbeatDaemon` with `current_job_id`.
6. `CommandExecutor` runs `subprocess.Popen` with 60s timeout. Subprocess completes with exit code 0.
7. Worker calls `JobRepository.mark_completed()`, updating state to `completed`, saving `stdout`, and creating audit entry in `execution_logs`.

### Scenario B: Transient Failure with Exponential Backoff
1. Worker claims job and executes command `curl https://api.example.com/data`.
2. Network call fails, subprocess returns exit code 1.
3. Worker calls `JobRepository.mark_failed()`.
4. `attempts` is incremented from 0 to 1 ($1 < \text{max\_retries}$).
5. Backoff delay is calculated: $2^1 = 2$ seconds.
6. `scheduled_at` is set to `NOW + 2 seconds`, `worker_id` set to `NULL`, and `state` set to `pending`.
7. After 2 seconds elapse, any available worker claims the job for attempt 2.

### Scenario C: Persistent Failure -> DLQ Routing
1. Job fails attempt 3 (where $\text{attempts} = 3 \ge \text{max\_retries} = 3$).
2. `JobRepository.mark_failed()` detects maximum retries exhausted.
3. Job state transitions to `DEAD`, `worker_id = NULL`, and error message recorded.
4. Job appears in `queuectl dlq list`.

### Scenario D: Manual Operator DLQ Reset
1. Operator inspects DLQ: `queuectl dlq list`.
2. Operator fixes downstream issue and runs `queuectl dlq retry <job_id>`.
3. `QueueService.retry_dlq_job()` resets `attempts = 0`, `state = 'pending'`, `scheduled_at = NOW`, and `error_message = NULL`.
4. Job is immediately claimed and executed cleanly.

### Scenario E: Unclean Worker Crash (`SIGKILL`) Recovery
1. Worker process PID 15056 claims job `J1` (`state = 'processing'`).
2. OS terminates PID 15056 with `SIGKILL` (kill -9). No cleanup runs.
3. Worker's heartbeat thread dies instantly. `last_heartbeat` remains frozen.
4. After 30 seconds, `CrashRecoveryService` runs.
5. Service detects PID 15056 `last_heartbeat` > 30s ago. Marks worker status `DEAD`.
6. Service finds `J1` in state `processing` owned by PID 15056.
7. Service increments attempts, clears `worker_id`, sets `state = 'pending'` and `scheduled_at = NOW`.
8. Healthy active workers claim `J1` and resume execution.
