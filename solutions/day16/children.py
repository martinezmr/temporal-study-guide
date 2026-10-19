"""Children that report back to their parent with a signal when done."""

from pydantic import BaseModel
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from solutions.shared.models import ComplianceInput, UpgradeInput


class RemediationDone(BaseModel):
    device: str
    ok: bool
    detail: str = ""


async def report_to_parent(done: RemediationDone) -> None:
    parent = workflow.info().parent
    if parent:  # also runnable standalone
        # No run ID: the signal reaches the parent's *current* run, even after continue-as-new.
        await workflow.get_external_workflow_handle(parent.workflow_id).signal("remediation_finished", done)


@workflow.defn(name="ConfigComplianceWorkflow")
class ConfigComplianceChild:
    @workflow.run
    async def run(self, inp: ComplianceInput) -> None:
        await workflow.sleep(600)  # pretend: 10 minutes of careful work
        await report_to_parent(RemediationDone(device=inp.device, ok=True, detail="compliance stub"))


@workflow.defn(name="DeviceUpgradeWorkflow")
class DeviceUpgradeChild:
    @workflow.run
    async def run(self, inp: UpgradeInput) -> None:
        await workflow.sleep(1800)
        await report_to_parent(RemediationDone(device=inp.device, ok=True, detail="upgrade stub"))
