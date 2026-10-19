from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from solutions.day25.activities import explain_drift
    from solutions.shared.activities import compute_drift, get_intent, get_running_config
    from solutions.shared.models import DriftExplanation

TASK_QUEUE = "solutions-day25"
ACT = {"start_to_close_timeout": timedelta(seconds=60)}
LLM_RETRY = RetryPolicy(initial_interval=timedelta(seconds=5), backoff_coefficient=2.0, maximum_attempts=4,
                        non_retryable_error_types=["LLMBadRequest"])


@workflow.defn
class ExplainDriftWorkflow:
    @workflow.run
    async def run(self, device: str) -> DriftExplanation | None:
        intent = await workflow.execute_activity(get_intent, device, **ACT)
        state = await workflow.execute_activity(get_running_config, device, **ACT)
        report = await workflow.execute_activity(compute_drift, args=[intent, state], **ACT)
        if not report.drifted:
            return None
        # Once this completes, the answer is in history: a worker crash never re-asks (or re-pays) the model.
        return await workflow.execute_activity(explain_drift, report, start_to_close_timeout=timedelta(seconds=90),
                                               retry_policy=LLM_RETRY)
