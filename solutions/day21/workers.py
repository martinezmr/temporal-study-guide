"""Two worker processes, one image.

    uv run python -m solutions.day21.workers orchestration
    uv run python -m solutions.day21.workers device-io
"""

import asyncio
import logging
import os
import signal
from datetime import timedelta

from solutions.day21.workflows import ORCHESTRATION_TASK_QUEUE, RoutedBackupWorkflow
from solutions.shared.activities import DEVICE_ACTIVITIES
from solutions.shared.runner import connect, make_worker, run
from solutions.shared.settings import DEVICE_IO_TASK_QUEUE


async def main(argv: list[str]) -> None:
    role = argv[0] if argv else os.environ.get("WORKER_ROLE", "orchestration")
    client = await connect()
    if role == "orchestration":
        worker = make_worker(client, ORCHESTRATION_TASK_QUEUE, workflows=[RoutedBackupWorkflow],
                             graceful_shutdown_timeout=timedelta(seconds=30))
    elif role == "device-io":
        worker = make_worker(
            client, DEVICE_IO_TASK_QUEUE, activities=DEVICE_ACTIVITIES,
            max_concurrent_activities=4,  # per worker process
            max_task_queue_activities_per_second=2.0,  # across ALL device-io workers: protects the switches
            graceful_shutdown_timeout=timedelta(seconds=30),  # let in-flight device calls finish on SIGTERM
        )
    else:
        raise SystemExit(f"unknown role {role!r}")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):  # OpenShift sends SIGTERM on pod shutdown
        loop.add_signal_handler(sig, stop.set)
    logging.info("worker role=%s build=%s", role, os.environ.get("BUILD_ID", "dev"))
    async with worker:  # leaving the block = graceful shutdown
        await stop.wait()
    logging.info("worker %s stopped cleanly", role)


if __name__ == "__main__":
    run(main)
