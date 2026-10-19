import pytest
from temporalio.client import WithStartWorkflowOperation, WorkflowUpdateFailedError
from temporalio.common import WorkflowIDConflictPolicy

from solutions.day10.workflows import DeviceWatchWorkflow, MaintenanceRequest, run_maintenance_task
from solutions.shared.activities import get_device_facts
from solutions.tests.helpers import local_env, wf_id, worker

ACTS = [get_device_facts, run_maintenance_task]


async def test_update_returns_ticket_and_validator_rejects():
    async with await local_env() as env:
        async with worker(env, "t", [DeviceWatchWorkflow], ACTS):
            h = await env.client.start_workflow(DeviceWatchWorkflow.run, args=["bos-rtr-01", 300],
                                                id=wf_id(), task_queue="t")
            ticket = await h.execute_update(DeviceWatchWorkflow.request_maintenance,
                                            MaintenanceRequest(id="r1", device="bos-rtr-01", task="clear-counters"))
            assert ticket.output == "clear-counters done on bos-rtr-01"
            with pytest.raises(WorkflowUpdateFailedError):
                await h.execute_update(DeviceWatchWorkflow.request_maintenance,
                                       MaintenanceRequest(id="r2", device="nyc-rtr-01", task="x"))
            await h.signal(DeviceWatchWorkflow.stop)
            assert await h.result() == 1


async def test_update_with_start_reuses_running_workflow():
    workflow_id = wf_id("watch")
    async with await local_env() as env:
        async with worker(env, "t", [DeviceWatchWorkflow], ACTS):
            run_ids = set()
            for i in range(2):
                op = WithStartWorkflowOperation(DeviceWatchWorkflow.run, args=["bos-rtr-01", 300], id=workflow_id,
                                                task_queue="t", id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING)
                await env.client.execute_update_with_start_workflow(
                    DeviceWatchWorkflow.request_maintenance,
                    MaintenanceRequest(id=f"r{i}", device="bos-rtr-01", task="t"), start_workflow_operation=op)
                run_ids.add((await op.workflow_handle()).result_run_id)
            assert len(run_ids) == 1
            await env.client.get_workflow_handle(workflow_id).signal(DeviceWatchWorkflow.stop)
