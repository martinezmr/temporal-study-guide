from datetime import datetime, timedelta

from pydantic import BaseModel
from temporalio import workflow
from temporalio.workflow import ParentClosePolicy

with workflow.unsafe.imports_passed_through():
    from solutions.day16.children import ConfigComplianceChild, DeviceUpgradeChild, RemediationDone
    from solutions.shared.drift_cycle import collect_drift
    from solutions.shared.models import ComplianceInput, DriftReport, UpgradeInput

TASK_QUEUE = "solutions-day16"
ORCHESTRATOR_ID = "d16-network-compliance-orchestrator"


class OrchestratorState(BaseModel):
    interval_minutes: int = 15
    max_concurrent: int = 2
    cycle: int = 0
    reports: list[DriftReport] = []
    in_flight: dict[str, str] = {}  # device -> child workflow ID
    pending: list[DriftReport] = []
    completed: list[RemediationDone] = []
    max_in_flight_seen: int = 0
    next_cycle_at: datetime | None = None
    max_cycles_per_run: int = 50
    stop_after_cycles: int | None = None  # tests: stop cycling, drain the queue, return


@workflow.defn
class NetworkComplianceOrchestrator:
    def __init__(self) -> None:
        self.s = OrchestratorState()
        self.check_requested = False
        self.slot_freed = False

    @workflow.run
    async def run(self, state: OrchestratorState) -> OrchestratorState:
        self.s = state
        cycles_this_run = 0
        while cycles_this_run < self.s.max_cycles_per_run and not workflow.info().is_continue_as_new_suggested():
            if self._cycle_due():
                self.s.reports, _ = await collect_drift()
                self.s.cycle += 1
                cycles_this_run += 1
                self.s.next_cycle_at = workflow.now() + timedelta(minutes=self.s.interval_minutes)
                self.check_requested = False
                self._enqueue()
            await self._dispatch()
            if self._finished():
                return self.s
            self.slot_freed = False
            try:
                await workflow.wait_condition(lambda: self.check_requested or self.slot_freed,
                                              timeout=self._until_next_cycle())
            except TimeoutError:
                pass
        await workflow.wait_condition(workflow.all_handlers_finished)
        workflow.continue_as_new(self.s)

    # ---- scheduling helpers ----

    def _cycles_allowed(self) -> bool:
        return self.s.stop_after_cycles is None or self.s.cycle < self.s.stop_after_cycles

    def _cycle_due(self) -> bool:
        if not self._cycles_allowed():
            return False
        return self.check_requested or self.s.next_cycle_at is None or workflow.now() >= self.s.next_cycle_at

    def _until_next_cycle(self) -> timedelta | None:
        if not self._cycles_allowed() or self.s.next_cycle_at is None:
            return None  # no more cycles: wait only for children
        return max(self.s.next_cycle_at - workflow.now(), timedelta(seconds=1))

    def _finished(self) -> bool:
        return not self._cycles_allowed() and not self.s.pending and not self.s.in_flight

    def _enqueue(self) -> None:
        queued = {r.device for r in self.s.pending}
        for r in self.s.reports:
            if r.drifted and r.device not in self.s.in_flight and r.device not in queued:
                self.s.pending.append(r)

    async def _dispatch(self) -> None:
        while self.s.pending and len(self.s.in_flight) < self.s.max_concurrent:
            r = self.s.pending.pop(0)
            if r.config_drift:
                child_id = f"d16-compliance-{r.device}"
                await workflow.start_child_workflow(
                    ConfigComplianceChild.run, ComplianceInput(device=r.device, missing_lines=r.missing_lines),
                    id=child_id, parent_close_policy=ParentClosePolicy.ABANDON)
            else:
                child_id = f"d16-upgrade-{r.device}"
                await workflow.start_child_workflow(
                    DeviceUpgradeChild.run, UpgradeInput(device=r.device, target_version=r.target_version),
                    id=child_id, parent_close_policy=ParentClosePolicy.ABANDON)
            self.s.in_flight[r.device] = child_id
            self.s.max_in_flight_seen = max(self.s.max_in_flight_seen, len(self.s.in_flight))

    # ---- messages ----

    @workflow.signal
    def remediation_finished(self, done: RemediationDone) -> None:
        self.s.in_flight.pop(done.device, None)
        self.s.completed.append(done)
        self.slot_freed = True

    @workflow.signal
    def force_check(self) -> None:
        self.check_requested = True

    @workflow.query
    def get_state(self) -> OrchestratorState:
        return self.s
