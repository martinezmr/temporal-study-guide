from datetime import timedelta

from pydantic import BaseModel
from temporalio import workflow
from temporalio.workflow import ParentClosePolicy

with workflow.unsafe.imports_passed_through():
    from solutions.day15.children import ConfigComplianceStub, DeviceUpgradeStub
    from solutions.shared.drift_cycle import collect_drift
    from solutions.shared.models import ComplianceInput, DriftReport, UpgradeInput

TASK_QUEUE = "solutions-day15"
ORCHESTRATOR_ID = "d15-network-compliance-orchestrator"


class OrchestratorState(BaseModel):
    interval_minutes: int = 15
    cycle: int = 0
    reports: list[DriftReport] = []
    children_started: list[str] = []  # Day 16 replaces this with in_flight/pending
    stop_after_cycles: int | None = None


@workflow.defn
class NetworkComplianceOrchestrator:
    def __init__(self) -> None:
        self.s = OrchestratorState()
        self.check_requested = False

    @workflow.run
    async def run(self, state: OrchestratorState) -> OrchestratorState:
        self.s = state
        for _ in range(50):
            self.s.reports, _unreachable = await collect_drift()
            self.s.cycle += 1
            await self.remediate()
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

    async def remediate(self) -> None:
        for r in self.s.reports:
            if not r.drifted:
                continue
            if r.config_drift:
                child_id = f"d15-compliance-{r.device}"
                if child_id in self.s.children_started:
                    continue
                await workflow.start_child_workflow(
                    ConfigComplianceStub.run, ComplianceInput(device=r.device, missing_lines=r.missing_lines),
                    id=child_id,
                    parent_close_policy=ParentClosePolicy.ABANDON,  # survive the parent's continue-as-new
                )
            else:
                child_id = f"d15-upgrade-{r.device}"
                if child_id in self.s.children_started:
                    continue
                await workflow.start_child_workflow(
                    DeviceUpgradeStub.run, UpgradeInput(device=r.device, target_version=r.target_version),
                    id=child_id,
                    parent_close_policy=ParentClosePolicy.ABANDON,
                )
            self.s.children_started.append(child_id)

    @workflow.query
    def get_state(self) -> OrchestratorState:
        return self.s

    @workflow.signal
    def force_check(self) -> None:
        self.check_requested = True
