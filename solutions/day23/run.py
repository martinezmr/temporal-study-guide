"""Day 23.

    uv run python -m solutions.day23.run setup
    uv run python -m solutions.day23.run demo bos-acc-01
  Break-it, separate processes:
    uv run python -m solutions.day23.run handler-worker
    uv run python -m solutions.day23.run caller-worker
    uv run python -m solutions.day23.run start bos-acc-01      # then stop/start the handler worker
    uv run python -m solutions.day23.run cancel bos-acc-01
"""

import argparse

from solutions.day17.workflows import ConfigComplianceWorkflow
from solutions.day23.handler import ComplianceServiceHandler
from solutions.day23.workflows import CALLER_TASK_QUEUE, ENDPOINT, HANDLER_TASK_QUEUE, RemediateViaNexusWorkflow
from solutions.shared.activities import DEVICE_ACTIVITIES
from solutions.shared.models import ComplianceInput
from solutions.shared.nexus_setup import ensure_endpoint
from solutions.shared.runner import connect, make_worker, run
from solutions.shared.settings import COMPLIANCE_NAMESPACE


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["setup", "handler-worker", "caller-worker", "start", "cancel", "demo"])
    p.add_argument("device", nargs="?", default="bos-acc-01")
    a = p.parse_args(argv)

    caller = await connect()
    if a.cmd == "setup":
        await ensure_endpoint(caller, ENDPOINT, COMPLIANCE_NAMESPACE, HANDLER_TASK_QUEUE)
        return
    handler_client = await connect(namespace=COMPLIANCE_NAMESPACE)
    handler_worker = make_worker(handler_client, HANDLER_TASK_QUEUE, [ConfigComplianceWorkflow], DEVICE_ACTIVITIES,
                                 nexus_service_handlers=[ComplianceServiceHandler()])
    caller_worker = make_worker(caller, CALLER_TASK_QUEUE, [RemediateViaNexusWorkflow])
    wf_id = f"d23-remediate-{a.device}"
    inp = ComplianceInput(device=a.device, missing_lines=["ntp server 10.0.0.1"])
    if a.cmd == "handler-worker":
        await handler_worker.run()
    elif a.cmd == "caller-worker":
        await caller_worker.run()
    elif a.cmd == "start":
        await caller.start_workflow(RemediateViaNexusWorkflow.run, inp, id=wf_id, task_queue=CALLER_TASK_QUEUE)
        print(f"started {wf_id}")
    elif a.cmd == "cancel":
        await caller.get_workflow_handle(wf_id).signal(RemediateViaNexusWorkflow.cancel_remediation)
    else:
        async with handler_worker, caller_worker:
            r = await caller.execute_workflow(RemediateViaNexusWorkflow.run, inp, id=wf_id, task_queue=CALLER_TASK_QUEUE)
            print(r.model_dump_json(indent=2) if r else "cancelled")


if __name__ == "__main__":
    run(main)
