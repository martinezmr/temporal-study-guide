"""Day 11.

    uv run python -m solutions.day11.run worker
    uv run python -m solutions.day11.run start bos-rtr-01       # waits until 02:00 Central
    uv run python -m solutions.day11.run override bos-rtr-01    # wake it now
"""

import argparse

from solutions.day11.workflows import TASK_QUEUE, MaintenanceWindowWorkflow, WindowInput
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "start", "override"])
    p.add_argument("device", nargs="?", default="bos-rtr-01")
    a = p.parse_args(argv)

    client = await connect()
    wf_id = f"d11-window-{a.device}"
    if a.cmd == "worker":
        await make_worker(client, TASK_QUEUE, [MaintenanceWindowWorkflow]).run()
    elif a.cmd == "start":
        await client.start_workflow(MaintenanceWindowWorkflow.run, WindowInput(device=a.device), id=wf_id,
                                    task_queue=TASK_QUEUE)
        print(f"{wf_id} is waiting for the window; see the timer under Pending in the UI")
    else:
        h = client.get_workflow_handle(wf_id)
        await h.signal(MaintenanceWindowWorkflow.override)
        print((await h.result()).model_dump_json())


if __name__ == "__main__":
    run(main)
