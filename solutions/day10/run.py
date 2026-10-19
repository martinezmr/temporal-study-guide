"""Day 10.

    uv run python -m solutions.day10.run worker
    uv run python -m solutions.day10.run maint bos-rtr-01 clear-counters          # update-with-start
    uv run python -m solutions.day10.run maint bos-rtr-01 clear-counters --wrong  # rejected by the validator
"""

import argparse
import uuid

from temporalio.client import WithStartWorkflowOperation, WorkflowUpdateFailedError
from temporalio.common import WorkflowIDConflictPolicy

from solutions.day10.workflows import TASK_QUEUE, DeviceWatchWorkflow, MaintenanceRequest, run_maintenance_task
from solutions.shared.activities import get_device_facts
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "maint"])
    p.add_argument("device", nargs="?", default="bos-rtr-01")
    p.add_argument("task", nargs="?", default="collect-facts")
    p.add_argument("--wrong", action="store_true", help="send the request for a different device")
    a = p.parse_args(argv)

    client = await connect()
    if a.cmd == "worker":
        await make_worker(client, TASK_QUEUE, [DeviceWatchWorkflow], [get_device_facts, run_maintenance_task]).run()
        return
    req = MaintenanceRequest(id=str(uuid.uuid4())[:8], device="nyc-acc-01" if a.wrong else a.device, task=a.task)
    start_op = WithStartWorkflowOperation(
        DeviceWatchWorkflow.run, args=[a.device, 300], id=f"d10-watch-{a.device}", task_queue=TASK_QUEUE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    try:
        ticket = await client.execute_update_with_start_workflow(
            DeviceWatchWorkflow.request_maintenance, req, start_workflow_operation=start_op)
        print(ticket.model_dump_json(indent=2))
    except WorkflowUpdateFailedError as e:
        print(f"rejected: {e.cause}")


if __name__ == "__main__":
    run(main)
