"""Day 24.

    uv run python -m solutions.day24.run setup
    uv run python -m solutions.day24.run demo bos-acc-01              # remediated
    uv run python -m solutions.day24.run demo lab-sw-99               # manual (rejected by the handler)
    uv run python -m solutions.day24.run demo bos-acc-01 --fail       # failed (verification), rolled back
"""

import argparse

from solutions.day17.workflows import ConfigComplianceWorkflow
from solutions.day24.handler import ComplianceServiceHandler
from solutions.day24.workflows import CALLER_TASK_QUEUE, ENDPOINT, HANDLER_TASK_QUEUE, RemediateWithPolicyWorkflow
from solutions.netops_contracts.compliance import ComplianceInput
from solutions.shared.activities import DEVICE_ACTIVITIES
from solutions.shared.nexus_setup import ensure_endpoint
from solutions.shared.runner import connect, make_worker, run
from solutions.shared.settings import COMPLIANCE_NAMESPACE


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["setup", "demo"])
    p.add_argument("device", nargs="?", default="bos-acc-01")
    p.add_argument("--fail", action="store_true")
    a = p.parse_args(argv)

    caller = await connect()
    if a.cmd == "setup":
        await ensure_endpoint(caller, ENDPOINT, COMPLIANCE_NAMESPACE, HANDLER_TASK_QUEUE)
        return
    handler_client = await connect(namespace=COMPLIANCE_NAMESPACE)
    inp = ComplianceInput(device=a.device, missing_lines=["ntp server 10.0.0.1"], force_verify_failure=a.fail)
    async with make_worker(handler_client, HANDLER_TASK_QUEUE, [ConfigComplianceWorkflow], DEVICE_ACTIVITIES,
                           nexus_service_handlers=[ComplianceServiceHandler()]), \
            make_worker(caller, CALLER_TASK_QUEUE, [RemediateWithPolicyWorkflow]):
        r = await caller.execute_workflow(RemediateWithPolicyWorkflow.run, inp, id=f"d24-remediate-{a.device}",
                                          task_queue=CALLER_TASK_QUEUE)
        print(r.model_dump_json(indent=2))


if __name__ == "__main__":
    run(main)
