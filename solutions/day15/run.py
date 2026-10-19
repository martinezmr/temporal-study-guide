"""Day 15.

    uv run python -m solutions.day15.run worker
    uv run python -m solutions.day15.run start
    # two children appear in the UI: d15-compliance-bos-acc-01, d15-upgrade-nyc-rtr-01
"""

import argparse

from temporalio.common import WorkflowIDConflictPolicy

from solutions.day15.children import ConfigComplianceStub, DeviceUpgradeStub
from solutions.day15.workflows import ORCHESTRATOR_ID, TASK_QUEUE, NetworkComplianceOrchestrator, OrchestratorState
from solutions.shared.activities import DEVICE_ACTIVITIES
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "start"])
    a = p.parse_args(argv)
    client = await connect()
    if a.cmd == "worker":
        wfs = [NetworkComplianceOrchestrator, ConfigComplianceStub, DeviceUpgradeStub]
        await make_worker(client, TASK_QUEUE, wfs, DEVICE_ACTIVITIES).run()
    else:
        await client.start_workflow(NetworkComplianceOrchestrator.run, OrchestratorState(), id=ORCHESTRATOR_ID,
                                    task_queue=TASK_QUEUE, id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING)
        print(f"started {ORCHESTRATOR_ID}")


if __name__ == "__main__":
    run(main)
