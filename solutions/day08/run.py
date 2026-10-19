"""Day 08.

    uv run python -m solutions.day08.run worker                   # terminal 1
    uv run python -m solutions.day08.run start bos-rtr-01         # terminal 2
    uv run python -m solutions.day08.run signal bos-rtr-01 pause  # pause | resume | force_check | stop
  or with the CLI:
    temporal workflow signal --workflow-id d08-watch-bos-rtr-01 --name force_check
"""

import argparse

from temporalio.common import WorkflowIDConflictPolicy

from solutions.day08.workflows import TASK_QUEUE, DeviceWatchWorkflow
from solutions.shared.activities import get_device_facts
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "start", "signal"])
    p.add_argument("device", nargs="?", default="bos-rtr-01")
    p.add_argument("signal_name", nargs="?", choices=["pause", "resume", "force_check", "stop"])
    p.add_argument("--interval", type=int, default=300)
    a = p.parse_args(argv)

    client = await connect()
    wf_id = f"d08-watch-{a.device}"
    if a.cmd == "worker":
        await make_worker(client, TASK_QUEUE, [DeviceWatchWorkflow], [get_device_facts]).run()
    elif a.cmd == "start":
        await client.start_workflow(DeviceWatchWorkflow.run, args=[a.device, a.interval], id=wf_id,
                                    task_queue=TASK_QUEUE, id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING)
        print(f"watching {a.device} as {wf_id}")
    else:
        handle = client.get_workflow_handle(wf_id)
        await handle.signal(a.signal_name)
        print(f"sent {a.signal_name}; checks so far: {await handle.query(DeviceWatchWorkflow.check_count)}")


if __name__ == "__main__":
    run(main)
