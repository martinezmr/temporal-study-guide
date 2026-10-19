"""Day 16.

    uv run python -m solutions.day16.run worker --drift-all     # mock: every device drifts
    uv run python -m solutions.day16.run start
    uv run python -m solutions.day16.run state                  # in_flight never exceeds 2
"""

import argparse

from temporalio.common import WorkflowIDConflictPolicy

from solutions.day16.children import ConfigComplianceChild, DeviceUpgradeChild
from solutions.day16.workflows import ORCHESTRATOR_ID, TASK_QUEUE, NetworkComplianceOrchestrator, OrchestratorState
from solutions.shared import mock_lab
from solutions.shared.activities import DEVICE_ACTIVITIES
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "start", "state"])
    p.add_argument("--drift-all", action="store_true")
    a = p.parse_args(argv)
    client = await connect()
    if a.cmd == "worker":
        if a.drift_all:
            for d in mock_lab.TOPOLOGY:
                mock_lab.remove_line(d, "logging host 10.0.0.50")
        wfs = [NetworkComplianceOrchestrator, ConfigComplianceChild, DeviceUpgradeChild]
        await make_worker(client, TASK_QUEUE, wfs, DEVICE_ACTIVITIES).run()
    elif a.cmd == "start":
        await client.start_workflow(NetworkComplianceOrchestrator.run, OrchestratorState(), id=ORCHESTRATOR_ID,
                                    task_queue=TASK_QUEUE, id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING)
    else:
        s = await client.get_workflow_handle(ORCHESTRATOR_ID).query(NetworkComplianceOrchestrator.get_state)
        print(f"cycle={s.cycle} in_flight={s.in_flight} pending={[r.device for r in s.pending]} "
              f"completed={len(s.completed)} max_in_flight_seen={s.max_in_flight_seen}")


if __name__ == "__main__":
    run(main)
