"""Day 14.

    uv run python -m solutions.day14.run worker
    uv run python -m solutions.day14.run start            # safe to run twice
    uv run python -m solutions.day14.run drift            # what's drifted right now
    uv run python -m solutions.day14.run signal force_check
    uv run python -m solutions.day14.run signal set_interval 5
"""

import argparse

from temporalio.common import WorkflowIDConflictPolicy

from solutions.day14.workflows import ORCHESTRATOR_ID, TASK_QUEUE, NetworkComplianceOrchestrator, OrchestratorState
from solutions.shared.activities import compute_drift, get_intent, get_running_config, list_devices
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "start", "drift", "signal"])
    p.add_argument("args", nargs="*")
    a = p.parse_args(argv)

    client = await connect()
    if a.cmd == "worker":
        acts = [list_devices, get_intent, get_running_config, compute_drift]
        await make_worker(client, TASK_QUEUE, [NetworkComplianceOrchestrator], acts).run()
    elif a.cmd == "start":
        await client.start_workflow(NetworkComplianceOrchestrator.run, OrchestratorState(), id=ORCHESTRATOR_ID,
                                    task_queue=TASK_QUEUE, id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING)
        print(f"orchestrator running as {ORCHESTRATOR_ID}")
    elif a.cmd == "drift":
        for r in await client.get_workflow_handle(ORCHESTRATOR_ID).query(NetworkComplianceOrchestrator.get_drift):
            print(f"{r.device:12} missing={r.missing_lines} version {r.running_version} -> {r.target_version}")
    else:
        name, *rest = a.args
        await client.get_workflow_handle(ORCHESTRATOR_ID).signal(name, *(int(x) for x in rest))
        print(f"sent {name}")


if __name__ == "__main__":
    run(main)
