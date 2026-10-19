"""Capstone workers. Same code, three roles (Day 30 runs each as a Deployment).

    uv run python -m solutions.day29.workers setup           # Nexus endpoint, once
    uv run python -m solutions.day29.workers compliance      # compliance namespace: Nexus handler + saga
    uv run python -m solutions.day29.workers device-io       # all device / Nautobot / LLM activities
    uv run python -m solutions.day29.workers orchestration   # orchestrator + children
    uv run python -m solutions.day29.workers start           # start (or attach to) the orchestrator
    uv run python -m solutions.day29.workers all             # all three roles in one process, for the lab
"""

import asyncio
import logging
import os
import signal
import sys

from temporalio.common import WorkflowIDConflictPolicy

from solutions.day17.workflows import ConfigComplianceWorkflow
from solutions.day24.handler import ComplianceServiceHandler
from solutions.day25.activities import explain_drift
from solutions.day27.activities import propose_remediation
from solutions.day27.workflows import ProposedRemediationWorkflow
from solutions.day29.upgrade import DeviceUpgradeWorkflow
from solutions.day29.workflows import (
    COMPLIANCE_TASK_QUEUE, ENDPOINT, ORCHESTRATION_TASK_QUEUE, ORCHESTRATOR_ID, NetworkComplianceOrchestrator,
    OrchestratorState,
)
from solutions.shared.activities import DEVICE_ACTIVITIES
from solutions.shared.nexus_setup import ensure_endpoint
from solutions.shared.runner import connect, make_worker
from solutions.shared.settings import COMPLIANCE_NAMESPACE, DEVICE_IO_TASK_QUEUE

ALL_ACTIVITIES = [*DEVICE_ACTIVITIES, explain_drift, propose_remediation]
CAPSTONE_WORKFLOWS = [NetworkComplianceOrchestrator, DeviceUpgradeWorkflow, ProposedRemediationWorkflow,
                      ConfigComplianceWorkflow]


async def build(role: str):
    if role == "compliance":
        client = await connect(namespace=COMPLIANCE_NAMESPACE)
        return [make_worker(client, COMPLIANCE_TASK_QUEUE, [ConfigComplianceWorkflow], DEVICE_ACTIVITIES,
                            nexus_service_handlers=[ComplianceServiceHandler()])]
    client = await connect()
    if role == "device-io":
        return [make_worker(client, DEVICE_IO_TASK_QUEUE, activities=ALL_ACTIVITIES, max_concurrent_activities=4,
                            max_task_queue_activities_per_second=2.0)]
    if role == "orchestration":
        # Child workflows (approval, upgrade, non-Nexus compliance) run their activities on this queue,
        # so it hosts the activities too. Route them to device-io (Day 21 style) as an extension exercise.
        return [make_worker(client, ORCHESTRATION_TASK_QUEUE, CAPSTONE_WORKFLOWS, ALL_ACTIVITIES)]
    raise SystemExit(f"unknown role {role}")


async def main(argv: list[str]) -> None:
    role = argv[0] if argv else os.environ.get("WORKER_ROLE", "all")
    if role == "setup":
        await ensure_endpoint(await connect(), ENDPOINT, COMPLIANCE_NAMESPACE, COMPLIANCE_TASK_QUEUE)
        return
    if role == "start":
        client = await connect()
        await client.start_workflow(
            NetworkComplianceOrchestrator.run, OrchestratorState(device_io_task_queue=DEVICE_IO_TASK_QUEUE),
            id=ORCHESTRATOR_ID, task_queue=ORCHESTRATION_TASK_QUEUE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING)
        print(f"orchestrator running as {ORCHESTRATOR_ID}")
        return
    roles = ["compliance", "device-io", "orchestration"] if role == "all" else [role]
    workers = [w for r in roles for w in await build(r)]

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    logging.info("running roles %s (build %s)", roles, os.environ.get("BUILD_ID", "dev"))
    await asyncio.gather(*(w.__aenter__() for w in workers))
    try:
        await stop.wait()
    finally:
        await asyncio.gather(*(w.__aexit__(None, None, None) for w in workers))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(main(sys.argv[1:]))
