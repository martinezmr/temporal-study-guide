"""ConfigComplianceWorkflow: the real one. Days 22-29 reuse it."""

from collections.abc import Awaitable, Callable
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    from solutions.shared.activities import (
        abort_session, commit_with_timer, confirm_commit, get_session_diff, stage_config, verify_compliance,
    )
    from solutions.shared.models import ComplianceInput, ComplianceResult

TASK_QUEUE = "solutions-day17"
ACT = {"start_to_close_timeout": timedelta(seconds=60), "retry_policy": RetryPolicy(maximum_attempts=3)}


@workflow.defn
class ConfigComplianceWorkflow:
    def __init__(self) -> None:
        self.stage = "starting"
        self.diff: list[str] = []

    @workflow.run
    async def run(self, inp: ComplianceInput) -> ComplianceResult:
        device = inp.device
        session = f"remediate-{str(workflow.uuid4())[:8]}"  # replay-safe unique name
        compensations: list[Callable[[], Awaitable]] = []
        try:
            self.stage = "staging"
            await workflow.execute_activity(stage_config, args=[device, session, inp.missing_lines], **ACT)
            compensations.append(lambda: workflow.execute_activity(abort_session, args=[device, session], **ACT))

            self.stage = "diffing"
            self.diff = await workflow.execute_activity(get_session_diff, args=[device, session], **ACT)
            if not self.diff:
                await self._compensate(compensations)
                return ComplianceResult(device=device, applied=False, detail="already compliant")

            self.stage = "committing with timer"  # the device rolls back on its own if we never confirm
            await workflow.execute_activity(commit_with_timer, args=[device, session, inp.commit_timer_minutes], **ACT)

            self.stage = "verifying"
            ok = await workflow.execute_activity(
                verify_compliance, args=[device, inp.missing_lines, inp.force_verify_failure], **ACT)
            if not ok:
                raise ApplicationError(f"{device}: verification failed after commit", type="VerificationFailed",
                                       non_retryable=True)

            self.stage = "confirming"
            await workflow.execute_activity(confirm_commit, args=[device, session], **ACT)
            self.stage = "done"
            return ComplianceResult(device=device, applied=True, diff=self.diff)
        except BaseException:
            # Covers activity failures, verification failure AND cancellation (asyncio.CancelledError).
            self.stage = "rolling back"
            await self._compensate(compensations)
            raise

    @staticmethod
    async def _compensate(compensations: list[Callable[[], Awaitable]]) -> None:
        for undo in reversed(compensations):
            await undo()
        compensations.clear()

    @workflow.query
    def progress(self) -> dict:
        return {"stage": self.stage, "diff": self.diff}
