"""The 'collect intent + state + diff for every device' step, reused by Days 15-29.

Called from workflow code (it uses workflow.execute_activity), so import it inside
imports_passed_through() like the activities. Day 14 shows the same logic inline.
"""

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from solutions.shared.activities import compute_drift, get_intent, get_running_config, list_devices
from solutions.shared.models import DriftReport


async def collect_drift(task_queue: str | None = None) -> tuple[list[DriftReport], list[str]]:
    """Returns (reports for reachable devices, unreachable device names)."""
    io = {"start_to_close_timeout": timedelta(seconds=60), "retry_policy": RetryPolicy(maximum_attempts=3)}
    if task_queue:
        io["task_queue"] = task_queue
    devices = await workflow.execute_activity(list_devices, **io)

    async def check(device: str) -> DriftReport:
        intent, state = await asyncio.gather(
            workflow.execute_activity(get_intent, device, **io),
            workflow.execute_activity(get_running_config, device, **io),
        )
        return await workflow.execute_activity(compute_drift, args=[intent, state], **io)

    results = await asyncio.gather(*[check(d) for d in devices], return_exceptions=True)
    reports = [r for r in results if isinstance(r, DriftReport)]
    unreachable = [d for d, r in zip(devices, results) if not isinstance(r, DriftReport)]
    return reports, unreachable
