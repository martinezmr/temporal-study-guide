"""Day 03.

    uv run python -m solutions.day03.run demo bos-rtr-01
    uv run python -m solutions.day03.run demo bos-rtr-01 --auth-fail   # fails once, no retries
    uv run python -m solutions.day03.run demo bos-rtr-01 --timeouts 2  # retried, then succeeds
"""

import argparse

from temporalio.client import WorkflowFailureError

from solutions.day03.workflows import TASK_QUEUE, FactsRequest, GetFactsV2Workflow
from solutions.shared import mock_lab
from solutions.shared.activities import get_device_facts
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "demo"])
    p.add_argument("device", nargs="?", default="bos-rtr-01")
    p.add_argument("--auth-fail", action="store_true")
    p.add_argument("--timeouts", type=int, default=0)
    a = p.parse_args(argv)

    client = await connect()
    worker = make_worker(client, TASK_QUEUE, [GetFactsV2Workflow], [get_device_facts])
    if a.cmd == "worker":
        await worker.run()
        return
    if a.auth_fail:
        mock_lab.fail_next(a.device, 1, kind="auth")
    mock_lab.fail_next(a.device, a.timeouts)
    async with worker:
        try:
            facts = await client.execute_workflow(
                GetFactsV2Workflow.run, FactsRequest(device=a.device), id=f"d03-facts-{a.device}", task_queue=TASK_QUEUE)
            print(facts.model_dump_json())
        except WorkflowFailureError as e:
            print(f"Workflow failed: {e.cause} <- {e.cause.cause}")
        print(f"eAPI calls made: {mock_lab.attempts(a.device)}")


if __name__ == "__main__":
    run(main)
