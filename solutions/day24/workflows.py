from datetime import timedelta
from typing import Literal

from pydantic import BaseModel
from temporalio import workflow
from temporalio.exceptions import NexusOperationError

with workflow.unsafe.imports_passed_through():
    from solutions.netops_contracts.compliance import ComplianceInput, ComplianceService

CALLER_TASK_QUEUE = "solutions-day24-caller"
HANDLER_TASK_QUEUE = "solutions-day24-compliance"
ENDPOINT = "d24-compliance-endpoint"


class RemediationOutcome(BaseModel):
    device: str
    status: Literal["remediated", "already-compliant", "manual", "failed"]
    detail: str = ""


@workflow.defn
class RemediateWithPolicyWorkflow:
    @workflow.run
    async def run(self, inp: ComplianceInput, timeout_minutes: int = 120) -> RemediationOutcome:
        nexus_client = workflow.create_nexus_client(service=ComplianceService, endpoint=ENDPOINT)
        try:
            result = await nexus_client.execute_operation(
                ComplianceService.remediate, inp, schedule_to_close_timeout=timedelta(minutes=timeout_minutes))
        except NexusOperationError as e:
            # Handler rejection, backing-workflow failure (e.g. VerificationFailed) or timeout all land here.
            cause = e.cause
            workflow.logger.warning("remediation of %s failed: %s", inp.device, cause)
            status = "manual" if "not under automated compliance" in str(cause) else "failed"
            return RemediationOutcome(device=inp.device, status=status, detail=str(cause))
        return RemediationOutcome(device=inp.device, status="remediated" if result.applied else "already-compliant",
                                  detail=result.detail)
