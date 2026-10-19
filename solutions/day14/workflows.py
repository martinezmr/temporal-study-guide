import asyncio
from datetime import datetime, timedelta

from pydantic import BaseModel
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from solutions.shared.activities import compute_drift, get_intent, get_running_config, list_devices
    from solutions.shared.models import DriftReport

TASK_QUEUE = "solutions-day14"
ORCHESTRATOR_ID = "d14-network-compliance-orchestrator"
IO = {"start_to_close_timeout": timedelta(seconds=60), "retry_policy": RetryPolicy(maximum_attempts=3)}


class OrchestratorState(BaseModel):
    interval_minutes: int = 15
    cycle: int = 0
    paused: bool = False
    reports: list[DriftReport] = []
    unreachable: list[str] = []
    last_cycle_at: datetime | None = None
    max_cycles_per_run: int = 50
    stop_after_cycles: int | None = None  # demos/tests only


@workflow.defn
class NetworkComplianceOrchestrator:
    def __init__(self) -> None:
        self.s = OrchestratorState()
        self.check_requested = False

    @workflow.run
    async def run(self, state: OrchestratorState) -> OrchestratorState:
        self.s = state
        cycles_this_run = 0
        while cycles_this_run < self.s.max_cycles_per_run and not workflow.info().is_continue_as_new_suggested():
            await workflow.wait_condition(lambda: not self.s.paused)
            await self.one_cycle()
            cycles_this_run += 1
            if self.s.stop_after_cycles is not None and self.s.cycle >= self.s.stop_after_cycles:
                return self.s
            self.check_requested = False
            try:
                await workflow.wait_condition(lambda: self.check_requested,
                                              timeout=timedelta(minutes=self.s.interval_minutes))
            except TimeoutError:
                pass
        await workflow.wait_condition(workflow.all_handlers_finished)
        workflow.continue_as_new(self.s)

    async def one_cycle(self) -> None:
        devices = await workflow.execute_activity(list_devices, **IO)

        async def check(device: str) -> DriftReport:
            intent, state = await asyncio.gather(
                workflow.execute_activity(get_intent, device, **IO),
                workflow.execute_activity(get_running_config, device, **IO),
            )
            return await workflow.execute_activity(compute_drift, args=[intent, state], **IO)

        results = await asyncio.gather(*[check(d) for d in devices], return_exceptions=True)
        self.s.reports = [r for r in results if isinstance(r, DriftReport)]
        self.s.unreachable = [d for d, r in zip(devices, results) if not isinstance(r, DriftReport)]
        self.s.cycle += 1
        self.s.last_cycle_at = workflow.now()
        drifted = [r.device for r in self.s.reports if r.drifted]
        workflow.logger.info("cycle %d: drifted=%s unreachable=%s", self.s.cycle, drifted, self.s.unreachable)

    # ---- control plane ----

    @workflow.query
    def get_drift(self) -> list[DriftReport]:
        return [r for r in self.s.reports if r.drifted]

    @workflow.query
    def get_state(self) -> OrchestratorState:
        return self.s

    @workflow.signal
    def pause(self) -> None:
        self.s.paused = True

    @workflow.signal
    def resume(self) -> None:
        self.s.paused = False

    @workflow.signal
    def force_check(self) -> None:
        self.check_requested = True

    @workflow.signal
    def set_interval(self, minutes: int) -> None:
        self.s.interval_minutes = max(1, minutes)
