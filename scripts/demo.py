"""
QueueCTL End-to-End Automated Showcase Demo Script.

Demonstrates job enqueueing, parallel worker execution, exponential backoff retries,
Dead Letter Queue (DLQ) routing, crash recovery, and status metrics.
"""

import time
import os
from pathlib import Path
from queuectl.config.settings import get_settings
from queuectl.database.connection import get_db_manager
from queuectl.database.migrations import init_db
from queuectl.models.job import JobCreate
from queuectl.services.metrics_service import MetricsService
from queuectl.services.queue_service import QueueService
from queuectl.services.worker_service import WorkerService


def _run_worker_process(db_path: str):
    """Top-level worker entrypoint for multiprocessing spawn."""
    from queuectl.workers.runner import WorkerRunner
    runner = WorkerRunner(db_path, worker_id="demo-worker-1")
    runner.start()


def main():
    print("=" * 70)
    print(" QUEUECTL END-TO-END DEMO SHOWCASE")
    print("=" * 70)

    demo_db = Path.home() / ".queuectl" / "demo_queuectl.db"
    if demo_db.exists():
        os.remove(demo_db)

    # Step 1: Initialize Database
    db_path = init_db(str(demo_db))
    db_manager = get_db_manager(db_path)
    queue_service = QueueService(db_manager)
    worker_service = WorkerService(db_manager)
    metrics_service = MetricsService(db_manager)

    print(f"\n[1] Database initialized at: {db_path}")

    # Step 2: Enqueue sample jobs
    print("\n[2] Enqueueing sample jobs...")
    
    j1 = queue_service.enqueue(JobCreate(name="Fast Success Job", command="python -c \"print('Task completed!')\"", priority=10))
    print(f"  + Enqueued Job 1: '{j1['name']}' (Priority 10)")

    j2 = queue_service.enqueue(JobCreate(name="Failing Job with Retry", command="python -c \"import sys; sys.exit(1)\"", max_retries=2, backoff_base=2.0))
    print(f"  + Enqueued Job 2: '{j2['name']}' (Will fail and retry twice -> DLQ)")

    j3 = queue_service.enqueue(JobCreate(name="Delayed Scheduled Job", command="echo Scheduled job executed!", delay_seconds=3))
    print(f"  + Enqueued Job 3: '{j3['name']}' (Scheduled with 3s delay)")

    # Step 3: Check System Status before worker
    status = metrics_service.get_system_status()
    print(f"\n[3] Initial Status: Total Jobs = {status['jobs']['total']} | Pending = {status['jobs']['pending']}")

    # Step 4: Launch Worker Process in background process
    print("\n[4] Starting Worker process to execute queued jobs...")
    import multiprocessing

    worker_proc = multiprocessing.Process(target=_run_worker_process, args=(db_path,))
    worker_proc.start()

    try:
        # Monitor execution for 10 seconds
        print("\n[5] Monitoring queue processing over 10 seconds...")
        for t in range(1, 11):
            time.sleep(1)
            st = metrics_service.get_system_status()
            j = st['jobs']
            print(f"  [{t}s] Pending: {j['pending']} | Processing: {j['processing']} | Completed: {j['completed']} | Dead (DLQ): {j['dead']}")

    finally:
        print("\n[6] Requesting graceful worker stop...")
        worker_service.stop_worker("demo-worker-1")
        worker_proc.join(timeout=5)
        if worker_proc.is_alive():
            worker_proc.terminate()

    # Step 5: Final Status Summary
    final_status = metrics_service.get_system_status()
    print("\n" + "=" * 70)
    print(" FINAL DEMO RESULTS SUMMARY")
    print("=" * 70)
    print(f" Total Jobs: {final_status['jobs']['total']}")
    print(f" Completed : {final_status['jobs']['completed']}")
    print(f" Dead (DLQ): {final_status['jobs']['dead']}")
    print(f" Pending   : {final_status['jobs']['pending']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
