import nexusrpc
import nexusrpc.handler
from temporalio import nexus

from solutions.day17.workflows import ConfigComplianceWorkflow
from solutions.day22.handler import POLICIES
from solutions.netops_contracts.compliance import (
    ComplianceInput, ComplianceResult, ComplianceService, Policy, PolicyRequest,
)

# The compliance team only remediates devices it has signed off on.
ALLOWED_DEVICES = {"bos-acc-01", "bos-rtr-01", "nyc-acc-01", "nyc-rtr-01"}


@nexusrpc.handler.service_handler(service=ComplianceService)
class ComplianceServiceHandler:
    @nexusrpc.handler.sync_operation
    async def get_policy(self, ctx: nexusrpc.handler.StartOperationContext, input: PolicyRequest) -> Policy:
        if input.role not in POLICIES:
            raise nexusrpc.HandlerError(f"no policy for role {input.role!r}", type=nexusrpc.HandlerErrorType.NOT_FOUND)
        return Policy(role=input.role, required_lines=POLICIES[input.role])

    @nexus.workflow_run_operation
    async def remediate(self, ctx: nexus.WorkflowRunOperationContext,
                        input: ComplianceInput) -> nexus.WorkflowHandle[ComplianceResult]:
        if input.device not in ALLOWED_DEVICES:
            # BAD_REQUEST is non-retryable: the caller gets a NexusOperationError right away.
            raise nexusrpc.HandlerError(f"{input.device} is not under automated compliance",
                                        type=nexusrpc.HandlerErrorType.BAD_REQUEST)
        return await ctx.start_workflow(ConfigComplianceWorkflow.run, input, id=f"d24-compliance-{input.device}")
