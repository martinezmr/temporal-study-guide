import asyncio
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from solutions.day23.service import ComplianceService
    from solutions.shared.models import ComplianceInput, ComplianceResult

CALLER_TASK_QUEUE = "solutions-day23-caller"
HANDLER_TASK_QUEUE = "solutions-day23-compliance"
ENDPOINT = "d23-compliance-endpoint"


@workflow.defn
class RemediateViaNexusWorkflow:
    """What the orchestrator does for one drifted device, minus everything else."""

    def __init__(self) -> None:
        self.cancel_requested = False

    @workflow.run
    async def run(self, inp: ComplianceInput) -> ComplianceResult | None:
        nexus_client = workflow.create_nexus_client(service=ComplianceService, endpoint=ENDPOINT)
        handle = await nexus_client.start_operation(ComplianceService.remediate, inp,
                                                    schedule_to_close_timeout=timedelta(hours=2))
        result = asyncio.create_task(self._result_of(handle))  # tasks are deterministic in workflows
        # Wait for the operation OR an operator's cancel request, whichever comes first.
        await workflow.wait_condition(lambda: result.done() or self.cancel_requested)
        if self.cancel_requested and not result.done():
            handle.cancel()  # delivered to ConfigComplianceWorkflow, whose saga rolls back
            try:
                await result
            except Exception as e:  # noqa: BLE001 - expected: the operation reports cancellation
                workflow.logger.info("remediation cancelled: %s", e)
            return None
        return await result

    @staticmethod
    async def _result_of(handle) -> ComplianceResult:
        return await handle

    @workflow.signal
    def cancel_remediation(self) -> None:
        self.cancel_requested = True
