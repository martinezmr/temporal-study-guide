"""How every caller talks to a device entity: update-with-start, so callers never care if it's running."""

from temporalio.client import Client, WithStartWorkflowOperation
from temporalio.common import WorkflowIDConflictPolicy

from solutions.day13.workflows import TASK_QUEUE, DeviceEntityInput, DeviceEntityWorkflow, DeviceRequest, RequestResult


async def submit_to_device(client: Client, device: str, req: DeviceRequest, task_queue: str = TASK_QUEUE) -> RequestResult:
    op = WithStartWorkflowOperation(
        DeviceEntityWorkflow.run, DeviceEntityInput(device=device), id=f"device-{device}", task_queue=task_queue,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return await client.execute_update_with_start_workflow(DeviceEntityWorkflow.submit, req, start_workflow_operation=op)
