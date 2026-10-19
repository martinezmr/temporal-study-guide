"""Day 12.

    uv run python -m solutions.day12.run worker
    uv run python -m solutions.day12.run start bos-rtr-01 --loops 3 --interval 10
    # watch the Run ID change every 3 checks in the UI, while the Workflow ID stays the same
    uv run python -m solutions.day12.run state bos-rtr-01
"""

import argparse

from temporalio.common import WorkflowIDConflictPolicy

from solutions.day12.workflows import TASK_QUEUE, DeviceWatchWorkflow, WatchInput
from solutions.shared.activities import get_device_facts
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "start", "state"])
    p.add_argument("device", nargs="?", default="bos-rtr-01")
    p.add_argument("--loops", type=int, default=3)
    p.add_argument("--interval", type=int, default=10)
    a = p.parse_args(argv)

    client = await connect()
    wf_id = f"d12-watch-{a.device}"
    if a.cmd == "worker":
        await make_worker(client, TASK_QUEUE, [DeviceWatchWorkflow], [get_device_facts]).run()
    elif a.cmd == "start":
        inp = WatchInput(device=a.device, interval_seconds=a.interval, max_loops_per_run=a.loops)
        await client.start_workflow(DeviceWatchWorkflow.run, inp, id=wf_id, task_queue=TASK_QUEUE,
                                    id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING)
        print(f"started {wf_id}")
    else:
        s = await client.get_workflow_handle(wf_id).query(DeviceWatchWorkflow.get_state)
        print(f"runs={s.runs} checks={s.checks} paused={s.paused}")


if __name__ == "__main__":
    run(main)
