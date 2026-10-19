"""Day 09.

    uv run python -m solutions.day09.run worker
    uv run python -m solutions.day09.run start bos-rtr-01 nyc-rtr-01
    uv run python -m solutions.day09.run status                # every watch workflow's status
    temporal workflow query --workflow-id d09-watch-bos-rtr-01 --type get_status
"""

import argparse

from temporalio.client import WorkflowExecutionStatus
from temporalio.common import WorkflowIDConflictPolicy

from solutions.day09.workflows import TASK_QUEUE, DeviceWatchWorkflow
from solutions.shared.activities import get_device_facts
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "start", "status"])
    p.add_argument("devices", nargs="*", default=["bos-rtr-01"])
    a = p.parse_args(argv)

    client = await connect()
    if a.cmd == "worker":
        await make_worker(client, TASK_QUEUE, [DeviceWatchWorkflow], [get_device_facts]).run()
    elif a.cmd == "start":
        for d in a.devices:
            await client.start_workflow(DeviceWatchWorkflow.run, args=[d, 60], id=f"d09-watch-{d}",
                                        task_queue=TASK_QUEUE, id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING)
            print(f"started d09-watch-{d}")
    else:
        async for wf in client.list_workflows('WorkflowType="DeviceWatchWorkflow" AND ExecutionStatus="Running"'):
            if wf.status != WorkflowExecutionStatus.RUNNING or not wf.id.startswith("d09-"):
                continue
            status = await client.get_workflow_handle(wf.id).query(DeviceWatchWorkflow.get_status)
            version = status.last_facts.version if status.last_facts else "-"
            print(f"{status.device:12} paused={status.paused!s:5} checks={status.checks:3} version={version} "
                  f"last={status.last_checked}")


if __name__ == "__main__":
    run(main)
