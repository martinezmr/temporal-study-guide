"""Day 04.

    uv run python -m solutions.day04.run demo bos-rtr-01
    uv run python -m solutions.day04.run broken           # watch the sandbox stop datetime.now()

  Break-it exercise (non-determinism), two terminals:
    uv run python -m solutions.day04.run worker
    uv run python -m solutions.day04.run start bos-rtr-01 --pause 60
    # stop the worker while it sleeps, then:
    uv run python -m solutions.day04.run worker --reordered
"""

import argparse

from solutions.day04.workflows import (
    TASK_QUEUE, BrokenClockWorkflow, QuietHoursInput, QuietHoursReordered, QuietHoursWorkflow,
)
from solutions.shared.activities import get_device_facts, get_lldp
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "start", "demo", "broken"])
    p.add_argument("device", nargs="?", default="bos-rtr-01")
    p.add_argument("--pause", type=int, default=0)
    p.add_argument("--reordered", action="store_true", help="run the 'bad deploy' version")
    a = p.parse_args(argv)

    client = await connect()
    wf = QuietHoursReordered if a.reordered else QuietHoursWorkflow
    worker = make_worker(client, TASK_QUEUE, [wf, BrokenClockWorkflow], [get_device_facts, get_lldp])
    if a.cmd == "worker":
        await worker.run()
    elif a.cmd == "start":
        h = await client.start_workflow(QuietHoursWorkflow.run, QuietHoursInput(device=a.device, pause_seconds=a.pause),
                                        id=f"d04-quiet-{a.device}", task_queue=TASK_QUEUE)
        print(f"started {h.id}; stop the worker during the {a.pause}s sleep, then restart with --reordered")
    elif a.cmd == "demo":
        async with worker:
            r = await client.execute_workflow(QuietHoursWorkflow.run, QuietHoursInput(device=a.device),
                                              id=f"d04-quiet-{a.device}", task_queue=TASK_QUEUE)
            print(r.model_dump_json(indent=2))
    else:
        h = await client.start_workflow(BrokenClockWorkflow.run, id="d04-broken", task_queue=TASK_QUEUE)
        print(f"started {h.id}. Run `worker` and watch the workflow task fail in the UI, then:")
        print("  temporal workflow terminate --workflow-id d04-broken")


if __name__ == "__main__":
    run(main)
