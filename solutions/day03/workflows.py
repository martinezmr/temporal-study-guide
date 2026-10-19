from datetime import timedelta

from pydantic import BaseModel
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from solutions.shared.activities import get_device_facts
    from solutions.shared.models import DeviceFacts

TASK_QUEUE = "solutions-day03"


class FactsRequest(BaseModel):
    """Single input object: add optional fields later without breaking running workflows."""

    device: str
    max_attempts: int = 5


@workflow.defn
class GetFactsV2Workflow:
    @workflow.run
    async def run(self, req: FactsRequest) -> DeviceFacts:
        return await workflow.execute_activity(
            get_device_facts,
            req.device,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                maximum_attempts=req.max_attempts,
                # Belt and braces: the eAPI client already raises AuthError as non-retryable.
                non_retryable_error_types=["AuthError", "UnknownDevice"],
            ),
        )
