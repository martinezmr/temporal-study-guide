"""Day 02.

    uv run python -m solutions.day02.run demo bos-rtr-01 nyc-rtr-01
    uv run python -m solutions.day02.run demo bos-rtr-01 --fail 3      # mock: 3 timeouts, then success
    DEVICE_MODE=live uv run --env-file .env python -m solutions.day02.run demo bos-rtr-01
"""

import argparse

from solutions.day02.workflows import TASK_QUEUE, GetFactsWorkflow
from solutions.shared import mock_lab
from solutions.shared.activities import get_device_facts
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "demo"])
    p.add_argument("devices", nargs="*", default=["bos-rtr-01"])
    p.add_argument("--fail", type=int, default=0, help="mock mode: fail this many times before succeeding")
    a = p.parse_args(argv)

    client = await connect()
    worker = make_worker(client, TASK_QUEUE, [GetFactsWorkflow], [get_device_facts])
    if a.cmd == "worker":
        await worker.run()
        return
    for d in a.devices:
        mock_lab.fail_next(d, a.fail)
    async with worker:
        for d in a.devices:
            facts = await client.execute_workflow(GetFactsWorkflow.run, d, id=f"d02-facts-{d}", task_queue=TASK_QUEUE)
            print(facts.model_dump_json())


if __name__ == "__main__":
    run(main)
