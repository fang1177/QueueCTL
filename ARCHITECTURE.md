# QueueCTL - System Architecture & Diagrams (ARCHITECTURE.md)

This document provides formal architectural models and visual sequence diagrams for **QueueCTL** created using Mermaid syntax.

---

## 1. System Component Diagram

```mermaid
graph TD
    subgraph CLI Layer
        CLI_Main["queuectl CLI (Typer)"]
        Cmd_Enqueue["queuectl enqueue"]
        Cmd_Worker["queuectl worker start/stop"]
        Cmd_Status["queuectl status / list"]
        Cmd_DLQ["queuectl dlq list/retry"]
    end

    subgraph Service & Core Layer
        QueueSvc["QueueService"]
        WorkerSvc["WorkerService"]
        RecoverySvc["CrashRecoveryService"]
        ConfigSvc["ConfigService"]
        MetricsSvc["MetricsService"]
        Executor["CommandExecutor (subprocess)"]
    end

    subgraph Persistence Layer (SQLite WAL)
        DB[("queuectl.db (SQLite WAL)")]
        Table_Jobs[("jobs Table")]
        Table_Workers[("workers Table")]
        Table_Config[("configuration Table")]
        Table_Logs[("execution_logs Table")]
    end

    subgraph Web UI Layer
        Dashboard["FastAPI Dashboard (http://localhost:8000)"]
    end

    CLI_Main --> Cmd_Enqueue
    CLI_Main --> Cmd_Worker
    CLI_Main --> Cmd_Status
    CLI_Main --> Cmd_DLQ

    Cmd_Enqueue --> QueueSvc
    Cmd_Worker --> WorkerSvc
    Cmd_Status --> MetricsSvc
    Cmd_DLQ --> QueueSvc

    WorkerSvc --> Executor
    WorkerSvc --> RecoverySvc

    QueueSvc --> DB
    WorkerSvc --> DB
    RecoverySvc --> DB
    MetricsSvc --> DB
    ConfigSvc --> DB

    Dashboard --> MetricsSvc
    Dashboard --> QueueSvc

    DB --> Table_Jobs
    DB --> Table_Workers
    DB --> Table_Config
    DB --> Table_Logs
```

---

## 2. Job Execution Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CLI as queuectl CLI
    participant QueueSrv as QueueService
    participant DB as SQLite DB (WAL)
    participant Worker as Worker Process
    participant Subproc as Subprocess Executor

    User->>CLI: queuectl enqueue --name "Backup" --command "tar -czf backup.tgz /data"
    CLI->>QueueSrv: enqueue(JobCreate)
    QueueSrv->>DB: INSERT INTO jobs (state='pending', priority=0)
    DB-->>QueueSrv: Job Created (ID: uuid)
    QueueSrv-->>CLI: Return Job Data
    CLI-->>User: [OK] Job Enqueued

    loop Worker Execution Loop
        Worker->>DB: BEGIN IMMEDIATE; UPDATE jobs SET state='processing', worker_id=W1 ... RETURNING id
        alt Job Available
            DB-->>Worker: Claimed Job (ID: uuid, command: "tar -czf ...")
            Worker->>Subproc: Popen(command, timeout=60)
            Subproc-->>Worker: Exit Code 0, stdout, stderr
            Worker->>DB: UPDATE jobs SET state='completed', output=stdout
            Worker->>DB: INSERT INTO execution_logs
        else Queue Empty
            DB-->>Worker: 0 rows updated
            Worker->>Worker: Sleep poll_interval (1s)
        end
    end
```

---

## 3. Worker Process Lifecycle State Diagram

```mermaid
stateDiagram-v2
    [*] --> Active: Worker Starts & Registers in DB (PID, Hostname)
    
    state Active {
        [*] --> Idle
        Idle --> ClaimingJob: Poll Queue
        ClaimingJob --> ExecutingJob: Atomic Claim Succeeded
        ClaimingJob --> Idle: Queue Empty
        ExecutingJob --> Idle: Job Completed / Failed
    }

    Active --> Stopping: queuectl worker stop (DB Status set to 'stopping')
    Active --> Dead: Heartbeat Silence > recovery_timeout (30s)

    Stopping --> Stopped: Finish Active Job & Exit Cleanly
    Dead --> [*]: Reclaimed by Crash Recovery Service

    Stopped --> [*]
```

---

## 4. Exponential Backoff & Retry Flowchart

```mermaid
flowchart TD
    Start([Job Claimed]) --> Exec[Execute Shell Command]
    Exec --> CheckExit{Exit Code == 0?}
    
    CheckExit -- Yes --> Success[Mark State = COMPLETED]
    CheckExit -- No --> IncAttempts[Increment Job Attempts + 1]

    IncAttempts --> CheckMaxRetries{attempts >= max_retries?}

    CheckMaxRetries -- Yes --> DLQ[Mark State = DEAD / Move to DLQ]
    CheckMaxRetries -- No --> CalcBackoff[Calculate Backoff Delay: base ^ attempts]

    CalcBackoff --> Schedule[Set scheduled_at = NOW + delay<br/>Set state = PENDING<br/>Set worker_id = NULL]
    Schedule --> End([Wait for Delay Expiration])
    DLQ --> EndDLQ([Wait for Manual DLQ Retry])
    Success --> EndComplete([Done])
```

---

## 5. SIGKILL Crash Recovery Engine Flowchart

```mermaid
flowchart TD
    Crash([Worker Process receives SIGKILL / kill -9]) --> HeartbeatStops[Heartbeat Loop Terminates Instantly]
    HeartbeatStops --> JobStuck[Job remains in 'processing' state in DB]

    WorkerCheck[Healthy Active Worker / Recovery Engine Runs] --> QueryStale[Query Workers where status IN 'active','stopping'<br/>AND last_heartbeat < NOW - 30s]

    QueryStale --> StaleFound{Stale Workers Found?}
    StaleFound -- No --> Sleep[Sleep Recovery Interval]
    StaleFound -- Yes --> MarkDead[Mark Worker Status = DEAD in DB]

    MarkDead --> QueryOrphaned[Find all Jobs assigned to Dead Worker with state = 'processing']

    QueryOrphaned --> LoopJobs{For Each Orphaned Job}
    LoopJobs --> CheckAttempts{attempts + 1 >= max_retries?}
    
    CheckAttempts -- Yes --> MoveDead[Mark State = DEAD<br/>Set Error = 'Worker Crashed']
    CheckAttempts -- No --> ResetPending[Mark State = PENDING<br/>Set scheduled_at = NOW<br/>Set worker_id = NULL]

    ResetPending --> NextJob[Reclaimed for Healthy Workers]
    MoveDead --> NextJob
```

---

## 6. Database Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    JOBS {
        string id PK
        string name
        string command
        string state
        int priority
        int attempts
        int max_retries
        float backoff_base
        int timeout
        datetime scheduled_at
        string worker_id FK
        text error_message
        text output
        datetime created_at
        datetime updated_at
        datetime started_at
        datetime completed_at
    }

    WORKERS {
        string id PK
        int pid
        string hostname
        string status
        datetime started_at
        datetime last_heartbeat
        string current_job_id
        int jobs_processed
        int jobs_failed
    }

    CONFIGURATION {
        string key PK
        string value
        datetime updated_at
    }

    EXECUTION_LOGS {
        int id PK
        string job_id FK
        string worker_id
        int attempt
        string status
        int exit_code
        text stdout
        text stderr
        text error_message
        float duration_ms
        datetime created_at
    }

    JOBS ||--o{ EXECUTION_LOGS : "generates audit logs"
    WORKERS ||--o{ JOBS : "claims and processes"
```
