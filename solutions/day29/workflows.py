"""NetworkComplianceOrchestrator: everything from the month, together."""

import asyncio
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from temporalio import workflow
from temporalio.common import RetryPolicy, SearchAttributePair, TypedSearchAttributes
from temporalio.workflow import ParentClosePolicy

with workflow.unsafe.imports_passed_through():
    from solutions.day17.workflows import ConfigComplianceWorkflow
    from solutions.day20.search_attributes import DEVICE_NAME
    from solutions.day25.activities import explain_drift
    from solutions.day27.workflows import ProposalInput, ProposedRemediationWorkflow
    from solutions.day29.upgrade import DeviceUpgradeWorkflow
    from solutions.netops_contracts.compliance import ComplianceService
    from solutions.shared.drift_cycle import collect_drift
    from solutions.shared.models import ComplianceInput, DriftExplanation, DriftReport, UpgradeInput

ORCHESTRATION_TASK_QUEUE = "solutions-capstone"
COMPLIANCE_TASK_QUEUE = "solutions-capstone-compliance"
ENDPOINT = "netops-compliance-endpoint"
ORCHESTRATOR_ID = "network-compliance-orchestrator"


class Outcome(BaseModel):
    device: str
    path: Literal["nexus", "child", "approval", "upgrade"]
    status: str
    detail: str = ""
    cycle: int = 0


class OrchestratorState(BaseModel):
    interval_minutes: int = 15
    max_concurrent: int = 2
    cycle: int = 0
    reports: list[DriftReport] = []
    unreachable: list[str] = []
    explanations: dict[str, DriftExplanation] = {}
    in_flight: dict[str, str] = {}  # device -> path
    pending: list[DriftReport] = []
    completed: list[Outcome] = []
    next_cycle_at: datetime | None = None
    paused: bool = False
    max_cycles_per_run: int = 50
    stop_after_cycles: int | None = None  # tests/demos
    # Wiring switches (production defaults; tests turn the external pieces off)
    use_nexus: bool = True
    use_search_attributes: bool = False  # True once Day 20's attributes are registered
    device_io_task_queue: str | None = None
    skip_windows: bool = False
    approval_timeout_minutes: int = 240


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
                await self._cycle()
                cycles_this_run += 1
            self._dispatch()
            if self._finished():
                await workflow.wait_condition(workflow.all_handlers_finished)
                return self.s
            self.slot_freed = False
            try:
                await workflow.wait_condition(lambda: self.check_requested or self.slot_freed,
                                              timeout=self._until_next_cycle())
            except TimeoutError:
                pass
        # Remediations are awaited by this run's tasks, so drain them before rolling over.
        await workflow.wait_condition(lambda: not self.s.in_flight and workflow.all_handlers_finished())
        workflow.continue_as_new(self.s)

    # ---- one detection cycle ----

    async def _cycle(self) -> None:
        self.s.reports, self.s.unreachable = await collect_drift(self.s.device_io_task_queue)
        self.s.cycle += 1
        self.s.next_cycle_at = workflow.now() + timedelta(minutes=self.s.interval_minutes)
        self.check_requested = False
        queued = {r.device for r in self.s.pending}
        for r in self.s.reports:
            if r.drifted and r.device not in self.s.in_flight and r.device not in queued:
                self.s.pending.append(r)
        workflow.logger.info("cycle %d: drifted=%s pending=%s in_flight=%s", self.s.cycle,
                             [r.device for r in self.s.reports if r.drifted], [r.device for r in self.s.pending],
                             list(self.s.in_flight))

    def _cycles_allowed(self) -> bool:
        return not self.s.paused and (self.s.stop_after_cycles is None or self.s.cycle < self.s.stop_after_cycles)

    def _cycle_due(self) -> bool:
        return self._cycles_allowed() and (self.check_requested or self.s.next_cycle_at is None
                                           or workflow.now() >= self.s.next_cycle_at)

    def _until_next_cycle(self) -> timedelta | None:
        if not self._cycles_allowed() or self.s.next_cycle_at is None:
            return None
        return max(self.s.next_cycle_at - workflow.now(), timedelta(seconds=1))

    def _finished(self) -> bool:
        return (self.s.stop_after_cycles is not None and self.s.cycle >= self.s.stop_after_cycles
                and not self.s.pending and not self.s.in_flight)

    # ---- remediation ----

    def _dispatch(self) -> None:
        while self.s.pending and len(self.s.in_flight) < self.s.max_concurrent and not self.s.paused:
            r = self.s.pending.pop(0)
            self.s.in_flight[r.device] = "starting"
            asyncio.create_task(self._remediate(r))  # deterministic task on the workflow's event loop

    async def _remediate(self, r: DriftReport) -> None:
        try:
            outcome = await self._route(r)
        except Exception as e:  # noqa: BLE001 - one device's failure must not stop the orchestrator
            path = self.s.in_flight.get(r.device, "child")
            outcome = Outcome(device=r.device, path=path if path in ("nexus", "child", "approval", "upgrade") else "child",
                              status="failed", detail=str(getattr(e, "cause", None) or e))
        outcome.cycle = self.s.cycle
        self.s.in_flight.pop(r.device, None)
        self.s.completed = (self.s.completed + [outcome])[-100:]  # keep state bounded
        self.slot_freed = True

    async def _route(self, r: DriftReport) -> Outcome:
        sa = TypedSearchAttributes([SearchAttributePair(DEVICE_NAME, r.device)]) if self.s.use_search_attributes else None
        if r.config_drift:
            explanation = await workflow.execute_activity(
                explain_drift, r, start_to_close_timeout=timedelta(seconds=90),
                task_queue=self.s.device_io_task_queue or workflow.info().task_queue,
                retry_policy=RetryPolicy(maximum_attempts=4, non_retryable_error_types=["LLMBadRequest"]))
            self.s.explanations[r.device] = explanation
            inp = ComplianceInput(device=r.device, missing_lines=r.missing_lines)

            if explanation.risk != "low":  # a human approves anything riskier than NTP/logging
                self.s.in_flight[r.device] = "approval"
                res = await workflow.execute_child_workflow(
                    ProposedRemediationWorkflow.run,
                    ProposalInput(device=r.device, approval_timeout_minutes=self.s.approval_timeout_minutes),
                    id=f"capstone-approval-{r.device}", parent_close_policy=ParentClosePolicy.ABANDON,
                    static_summary=f"[{explanation.risk}] {explanation.summary}"[:200], search_attributes=sa)
                return Outcome(device=r.device, path="approval", status=res.status, detail=res.approver)

            if self.s.use_nexus:  # low risk: the compliance team's service fixes it
                self.s.in_flight[r.device] = "nexus"
                nexus = workflow.create_nexus_client(service=ComplianceService, endpoint=ENDPOINT)
                res = await nexus.execute_operation(ComplianceService.remediate, inp,
                                                    schedule_to_close_timeout=timedelta(hours=2))
                return Outcome(device=r.device, path="nexus", status="remediated" if res.applied else "no-op",
                               detail=res.detail)

            self.s.in_flight[r.device] = "child"  # same thing without Nexus (tests, single-namespace setups)
            res = await workflow.execute_child_workflow(
                ConfigComplianceWorkflow.run, inp, id=f"capstone-compliance-{r.device}",
                parent_close_policy=ParentClosePolicy.ABANDON, static_summary=explanation.summary[:200],
                search_attributes=sa)
            return Outcome(device=r.device, path="child", status="remediated" if res.applied else "no-op",
                           detail=res.detail)

        self.s.in_flight[r.device] = "upgrade"
        res = await workflow.execute_child_workflow(
            DeviceUpgradeWorkflow.run,
            UpgradeInput(device=r.device, target_version=r.target_version, skip_window=self.s.skip_windows),
            id=f"capstone-upgrade-{r.device}", parent_close_policy=ParentClosePolicy.ABANDON,
            static_summary=f"Upgrade {r.device}: {r.running_version} -> {r.target_version}", search_attributes=sa)
        return Outcome(device=r.device, path="upgrade", status="upgraded" if res.upgraded else "no-op",
                       detail=res.detail)

    # ---- control plane ----

    @workflow.query
    def get_state(self) -> OrchestratorState:
        return self.s

    @workflow.query
    def get_drift(self) -> list[DriftReport]:
        return [r for r in self.s.reports if r.drifted]

    @workflow.signal
    def force_check(self) -> None:
        self.check_requested = True

    @workflow.signal
    def pause(self) -> None:
        self.s.paused = True

    @workflow.signal
    def resume(self) -> None:
        self.s.paused = False
        self.check_requested = True

    @workflow.signal
    def set_interval(self, minutes: int) -> None:
        self.s.interval_minutes = max(1, minutes)
