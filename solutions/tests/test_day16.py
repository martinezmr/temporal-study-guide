from solutions.day16.children import ConfigComplianceChild, DeviceUpgradeChild
from solutions.day16.workflows import NetworkComplianceOrchestrator, OrchestratorState
from solutions.shared import mock_lab
from solutions.tests.helpers import time_skipping_env, wf_id, worker


async def test_cap_and_no_duplicates():
    for d in mock_lab.TOPOLOGY:
        mock_lab.remove_line(d, "logging host 10.0.0.50")  # all 4 devices drift
    async with await time_skipping_env() as env:
        async with worker(env, "t", [NetworkComplianceOrchestrator, ConfigComplianceChild, DeviceUpgradeChild]):
            final = await env.client.execute_workflow(
                NetworkComplianceOrchestrator.run, OrchestratorState(stop_after_cycles=1, max_concurrent=2),
                id=wf_id(), task_queue="t")
    assert sorted(d.device for d in final.completed) == sorted(mock_lab.TOPOLOGY)  # each device exactly once
    assert final.max_in_flight_seen == 2
    assert not final.in_flight and not final.pending
