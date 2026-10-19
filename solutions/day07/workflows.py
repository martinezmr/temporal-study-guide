import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from solutions.shared.activities import build_backup_report, get_running_config, list_devices, save_backups
    from solutions.shared.models import BackupReport, DeviceState

TASK_QUEUE = "solutions-day07"


@workflow.defn
class BackupConfigsWorkflow:
    @workflow.run
    async def run(self) -> BackupReport:
        devices = await workflow.execute_activity(list_devices, start_to_close_timeout=timedelta(seconds=30))

        # Fan out: one activity per device, all in flight at once.
        results = await asyncio.gather(
            *[
                workflow.execute_activity(
                    get_running_config,
                    d,
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
                for d in devices
            ],
            return_exceptions=True,  # one bad device must not lose the other three
        )
        report = build_backup_report(devices, results)
        ok = [r for r in results if isinstance(r, DeviceState)]
        for d, r in zip(devices, results):
            if not isinstance(r, DeviceState):
                workflow.logger.warning("Backup failed for %s: %s", d, r)
        if ok:
            await workflow.execute_activity(save_backups, ok, start_to_close_timeout=timedelta(seconds=30))
        return report
