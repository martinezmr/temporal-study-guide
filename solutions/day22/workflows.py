"""Lives with the 'NetOps platform team', in the default namespace."""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from solutions.day22.service import ComplianceService, Policy, PolicyRequest

CALLER_TASK_QUEUE = "solutions-day22-caller"
HANDLER_TASK_QUEUE = "solutions-day22-compliance"
ENDPOINT = "d22-compliance-endpoint"


@workflow.defn
class PolicyCallerWorkflow:
    @workflow.run
    async def run(self, role: str) -> Policy:
        nexus_client = workflow.create_nexus_client(service=ComplianceService, endpoint=ENDPOINT)
        return await nexus_client.execute_operation(
            ComplianceService.get_policy, PolicyRequest(role=role), schedule_to_close_timeout=timedelta(seconds=30))
