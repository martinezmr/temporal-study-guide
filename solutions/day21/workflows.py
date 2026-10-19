"""Backup + drift check with activities routed to the device-io task queue."""

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from solutions.shared.activities import build_backup_report, get_running_config, list_devices, save_backups
    from solutions.shared.models import BackupReport, DeviceState
    from solutions.shared.settings import DEVICE_IO_TASK_QUEUE

ORCHESTRATION_TASK_QUEUE = "solutions-day21-orchestration"
IO = {
    "task_queue": DEVICE_IO_TASK_QUEUE,  # <- the routing: these run only on device-io workers
    "start_to_close_timeout": timedelta(seconds=60),
    "retry_policy": RetryPolicy(maximum_attempts=3),
}


@workflow.defn
class RoutedBackupWorkflow:
    @workflow.run
    async def run(self) -> BackupReport:
        devices = await workflow.execute_activity(list_devices, **IO)
        results = await asyncio.gather(*[workflow.execute_activity(get_running_config, d, **IO) for d in devices],
                                       return_exceptions=True)
        ok = [r for r in results if isinstance(r, DeviceState)]
        if ok:
            await workflow.execute_activity(save_backups, ok, **IO)
        return build_backup_report(devices, results)
