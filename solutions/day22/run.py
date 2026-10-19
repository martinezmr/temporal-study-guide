"""Day 22.

    uv run python -m solutions.day22.run setup           # creates the endpoint (once)
    uv run python -m solutions.day22.run demo access     # runs both workers in-process and calls get_policy
  or as separate processes:
    uv run python -m solutions.day22.run handler-worker
    uv run python -m solutions.day22.run caller-worker
    uv run python -m solutions.day22.run call access
"""

import argparse

from solutions.day22.handler import ComplianceServiceHandler
from solutions.day22.workflows import CALLER_TASK_QUEUE, ENDPOINT, HANDLER_TASK_QUEUE, PolicyCallerWorkflow
from solutions.shared.nexus_setup import ensure_endpoint
from solutions.shared.runner import connect, make_worker, run
from solutions.shared.settings import COMPLIANCE_NAMESPACE


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["setup", "handler-worker", "caller-worker", "call", "demo"])
    p.add_argument("role", nargs="?", default="access")
    a = p.parse_args(argv)

    caller = await connect()  # default namespace
    if a.cmd == "setup":
        await ensure_endpoint(caller, ENDPOINT, COMPLIANCE_NAMESPACE, HANDLER_TASK_QUEUE)
        return
    handler_client = await connect(namespace=COMPLIANCE_NAMESPACE)
    handler_worker = make_worker(handler_client, HANDLER_TASK_QUEUE, nexus_service_handlers=[ComplianceServiceHandler()])
    caller_worker = make_worker(caller, CALLER_TASK_QUEUE, [PolicyCallerWorkflow])
    if a.cmd == "handler-worker":
        await handler_worker.run()
    elif a.cmd == "caller-worker":
        await caller_worker.run()
    elif a.cmd == "call":
        print(await caller.execute_workflow(PolicyCallerWorkflow.run, a.role, id=f"d22-policy-{a.role}",
                                            task_queue=CALLER_TASK_QUEUE))
    else:
        async with handler_worker, caller_worker:
            print(await caller.execute_workflow(PolicyCallerWorkflow.run, a.role, id=f"d22-policy-{a.role}",
                                                task_queue=CALLER_TASK_QUEUE))


if __name__ == "__main__":
    run(main)
