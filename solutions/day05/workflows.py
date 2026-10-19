from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from solutions.shared.activities import collect_show_tech, get_lldp_neighbors

TASK_QUEUE = "solutions-day05"


@workflow.defn
class ShowTechWorkflow:
    @workflow.run
    async def run(self, device: str) -> list[str]:
        return await workflow.execute_activity(
            collect_show_tech,
            device,
            start_to_close_timeout=timedelta(minutes=10),
            heartbeat_timeout=timedelta(seconds=15),  # no heartbeat for 15 s = attempt failed
            retry_policy=RetryPolicy(maximum_attempts=5),
        )


@workflow.defn
class LldpWorkflow:
    @workflow.run
    async def run(self, device: str) -> list[dict]:
        # Sync activity: runs in the worker's ThreadPoolExecutor, never blocks the event loop.
        return await workflow.execute_activity(get_lldp_neighbors, device, start_to_close_timeout=timedelta(seconds=30))
