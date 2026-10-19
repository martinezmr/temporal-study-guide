from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from solutions.shared.activities import get_device_facts
    from solutions.shared.models import DeviceFacts

TASK_QUEUE = "solutions-day02"

FACTS_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=5,
)


@workflow.defn
class GetFactsWorkflow:
    @workflow.run
    async def run(self, device: str) -> DeviceFacts:
        return await workflow.execute_activity(
            get_device_facts,
            device,
            start_to_close_timeout=timedelta(seconds=30),  # one attempt
            retry_policy=FACTS_RETRY,
        )
