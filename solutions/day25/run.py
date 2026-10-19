"""Day 25.

    uv run python -m solutions.day25.run demo bos-acc-01 nyc-rtr-01                 # mock explanation
    ANTHROPIC_API_KEY=sk-... uv run python -m solutions.day25.run demo bos-acc-01   # real model
"""

import argparse

from solutions.day25.activities import explain_drift
from solutions.day25.workflows import TASK_QUEUE, ExplainDriftWorkflow
from solutions.shared.activities import DEVICE_ACTIVITIES
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "demo"])
    p.add_argument("devices", nargs="*", default=["bos-acc-01"])
    a = p.parse_args(argv)
    client = await connect()
    worker = make_worker(client, TASK_QUEUE, [ExplainDriftWorkflow], [*DEVICE_ACTIVITIES, explain_drift])
    if a.cmd == "worker":
        await worker.run()
        return
    async with worker:
        for d in a.devices:
            r = await client.execute_workflow(ExplainDriftWorkflow.run, d, id=f"d25-explain-{d}", task_queue=TASK_QUEUE)
            print(f"{d}: {r.model_dump_json(indent=2) if r else 'compliant'}")


if __name__ == "__main__":
    run(main)
