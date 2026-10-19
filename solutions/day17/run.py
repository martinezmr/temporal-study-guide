"""Day 17.

    uv run python -m solutions.day17.run demo bos-acc-01                 # fixes the missing ntp line
    uv run python -m solutions.day17.run demo bos-acc-01 --fail-verify   # watch the rollback
    DEVICE_MODE=live uv run --env-file .env python -m solutions.day17.run demo bos-acc-01 --line "ntp server 10.0.0.1"
"""

import argparse

from temporalio.client import WorkflowFailureError

from solutions.day17.workflows import TASK_QUEUE, ConfigComplianceWorkflow
from solutions.shared import mock_lab, settings
from solutions.shared.activities import DEVICE_ACTIVITIES
from solutions.shared.models import ComplianceInput
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "demo"])
    p.add_argument("device", nargs="?", default="bos-acc-01")
    p.add_argument("--line", action="append", default=None, help="config line(s) to enforce")
    p.add_argument("--fail-verify", action="store_true")
    a = p.parse_args(argv)

    client = await connect()
    worker = make_worker(client, TASK_QUEUE, [ConfigComplianceWorkflow], DEVICE_ACTIVITIES)
    if a.cmd == "worker":
        await worker.run()
        return
    lines = a.line or ["ntp server 10.0.0.1"]
    inp = ComplianceInput(device=a.device, missing_lines=lines, force_verify_failure=a.fail_verify)
    async with worker:
        try:
            r = await client.execute_workflow(ConfigComplianceWorkflow.run, inp, id=f"d17-compliance-{a.device}",
                                              task_queue=TASK_QUEUE)
            print(r.model_dump_json(indent=2))
        except WorkflowFailureError as e:
            print(f"failed and rolled back: {e.cause}")
    if settings.device_mode() == "mock":
        print("device now has:", [line for line in mock_lab.config_of(a.device) if line.startswith("ntp")])


if __name__ == "__main__":
    run(main)
