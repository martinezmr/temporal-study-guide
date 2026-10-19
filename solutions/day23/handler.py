import nexusrpc
import nexusrpc.handler
from temporalio import nexus

from solutions.day17.workflows import ConfigComplianceWorkflow
from solutions.day22.handler import POLICIES
from solutions.day22.service import Policy, PolicyRequest
from solutions.day23.service import ComplianceService
from solutions.shared.models import ComplianceInput, ComplianceResult


@nexusrpc.handler.service_handler(service=ComplianceService)
class ComplianceServiceHandler:
    @nexusrpc.handler.sync_operation
    async def get_policy(self, ctx: nexusrpc.handler.StartOperationContext, input: PolicyRequest) -> Policy:
        return Policy(role=input.role, required_lines=POLICIES[input.role])

    @nexus.workflow_run_operation
    async def remediate(self, ctx: nexus.WorkflowRunOperationContext,
                        input: ComplianceInput) -> nexus.WorkflowHandle[ComplianceResult]:
        # Starts ConfigComplianceWorkflow in THIS (compliance) namespace on the handler's task queue.
        # Deterministic ID: a second request for the same device while one runs can't start a duplicate.
        return await ctx.start_workflow(ConfigComplianceWorkflow.run, input, id=f"d23-compliance-{input.device}")
