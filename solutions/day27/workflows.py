from datetime import timedelta
from typing import Literal

from pydantic import BaseModel
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    from solutions.day27.activities import Proposal, propose_remediation
    from solutions.shared.activities import (
        abort_session, commit_with_timer, compute_drift, confirm_commit, get_intent, get_running_config,
        get_session_diff, stage_config, verify_compliance,
    )

TASK_QUEUE = "solutions-day27"
ACT = {"start_to_close_timeout": timedelta(seconds=60), "retry_policy": RetryPolicy(maximum_attempts=3)}
APPROVERS = {"manny", "netops-oncall"}
FORBIDDEN = ("reload", "write erase", "erase ", "no aaa", "delete ", "zerotouch")


class ProposalInput(BaseModel):
    device: str
    approval_timeout_minutes: int = 240


class Decision(BaseModel):
    approved: bool
    approver: str
    comment: str = ""


class ProposalView(BaseModel):
    stage: str
    proposal: Proposal | None = None
    device_diff: list[str] = []  # from the DEVICE, not the model's description
    decision: Decision | None = None


class ProposalOutcome(BaseModel):
    device: str
    status: Literal["applied", "rejected", "timed-out", "nothing-to-do", "failed"]
    diff: list[str] = []
    reasoning: str = ""
    approver: str = ""


@workflow.defn
class ProposedRemediationWorkflow:
    def __init__(self) -> None:
        self.view = ProposalView(stage="analysing")

    @workflow.run
    async def run(self, inp: ProposalInput) -> ProposalOutcome:
        d = inp.device
        intent = await workflow.execute_activity(get_intent, d, **ACT)
        state = await workflow.execute_activity(get_running_config, d, **ACT)
        report = await workflow.execute_activity(compute_drift, args=[intent, state], **ACT)
        if not report.config_drift:
            self.view.stage = "done"
            return ProposalOutcome(device=d, status="nothing-to-do")

        # 1. The model proposes. Deterministic guardrail on its output before anything touches the device.
        proposal = await workflow.execute_activity(propose_remediation, report, start_to_close_timeout=timedelta(seconds=90),
                                                   retry_policy=RetryPolicy(maximum_attempts=3,
                                                                            non_retryable_error_types=["LLMBadRequest"]))
        bad = [line for line in proposal.lines if any(f in line.lower() for f in FORBIDDEN)]
        if bad:
            raise ApplicationError(f"unsafe proposal rejected: {bad}", type="UnsafeProposal", non_retryable=True)
        self.view.proposal = proposal

        # 2. Stage it and record the REAL diff from the device.
        session = f"proposal-{str(workflow.uuid4())[:8]}"
        self.view.stage = "staging"
        await workflow.execute_activity(stage_config, args=[d, session, proposal.lines], **ACT)
        self.view.device_diff = await workflow.execute_activity(get_session_diff, args=[d, session], **ACT)

        # 3. Wait for a human, with a deadline. No answer = no change.
        self.view.stage = "awaiting-approval"
        try:
            await workflow.wait_condition(lambda: self.view.decision is not None,
                                          timeout=timedelta(minutes=inp.approval_timeout_minutes))
        except TimeoutError:
            self.view.stage = "timed-out"
            await workflow.execute_activity(abort_session, args=[d, session], **ACT)
            return ProposalOutcome(device=d, status="timed-out", diff=self.view.device_diff, reasoning=proposal.reasoning)

        decision = self.view.decision
        if not decision.approved:
            self.view.stage = "rejected"
            await workflow.execute_activity(abort_session, args=[d, session], **ACT)
            return ProposalOutcome(device=d, status="rejected", diff=self.view.device_diff,
                                   reasoning=proposal.reasoning, approver=decision.approver)

        # 4. Approved: the deterministic commit / verify / confirm path from Day 17.
        self.view.stage = "applying"
        await workflow.execute_activity(commit_with_timer, args=[d, session, 5], **ACT)
        if not await workflow.execute_activity(verify_compliance, args=[d, proposal.lines, False], **ACT):
            await workflow.execute_activity(abort_session, args=[d, session], **ACT)
            self.view.stage = "failed"
            return ProposalOutcome(device=d, status="failed", diff=self.view.device_diff, approver=decision.approver)
        await workflow.execute_activity(confirm_commit, args=[d, session], **ACT)
        self.view.stage = "applied"
        return ProposalOutcome(device=d, status="applied", diff=self.view.device_diff, reasoning=proposal.reasoning,
                               approver=decision.approver)

    @workflow.update
    def decide(self, decision: Decision) -> str:
        self.view.decision = decision
        return f"recorded: {'approved' if decision.approved else 'rejected'} by {decision.approver}"

    @decide.validator
    def validate_decision(self, decision: Decision) -> None:
        if self.view.stage != "awaiting-approval":
            raise ValueError(f"not awaiting approval (stage: {self.view.stage})")
        if self.view.decision is not None:
            raise ValueError("already decided")
        if decision.approver not in APPROVERS:
            raise ValueError(f"{decision.approver} is not an approver")

    @workflow.query
    def get_proposal(self) -> ProposalView:
        return self.view
