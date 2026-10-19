"""Day 05.

    uv run python -m solutions.day05.run demo bos-rtr-01
  Heartbeat exercise, two terminals:
    uv run python -m solutions.day05.run worker --delay 5     # each command takes 5 s
    uv run python -m solutions.day05.run start bos-rtr-01
    # Ctrl-C the worker after 2-3 commands, wait ~15 s, restart it: it resumes from the last heartbeat.
"""

import argparse

from solutions.day05.workflows import TASK_QUEUE, LldpWorkflow, ShowTechWorkflow
from solutions.shared import mock_lab
from solutions.shared.activities import collect_show_tech, get_lldp_neighbors
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "start", "demo"])
    p.add_argument("device", nargs="?", default="bos-rtr-01")
    p.add_argument("--delay", type=float, default=1.0, help="mock: seconds per show-tech command")
    a = p.parse_args(argv)
    mock_lab.SHOW_TECH_DELAY = a.delay

    client = await connect()
    worker = make_worker(client, TASK_QUEUE, [ShowTechWorkflow, LldpWorkflow], [collect_show_tech, get_lldp_neighbors])
    if a.cmd == "worker":
        await worker.run()
    elif a.cmd == "start":
        h = await client.start_workflow(ShowTechWorkflow.run, a.device, id=f"d05-showtech-{a.device}",
                                        task_queue=TASK_QUEUE)
        print(f"started {h.id}")
    else:
        async with worker:
            print(await client.execute_workflow(LldpWorkflow.run, a.device, id=f"d05-lldp-{a.device}",
                                                task_queue=TASK_QUEUE))
            out = await client.execute_workflow(ShowTechWorkflow.run, a.device, id=f"d05-showtech-{a.device}",
                                                task_queue=TASK_QUEUE)
            print(f"collected {len(out)} sections")


if __name__ == "__main__":
    run(main)
