from solutions.day15.children import ConfigComplianceStub, DeviceUpgradeStub
from solutions.day15.workflows import NetworkComplianceOrchestrator, OrchestratorState
from solutions.tests.helpers import time_skipping_env, wf_id, worker


async def test_starts_one_child_per_drifted_device():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [NetworkComplianceOrchestrator, ConfigComplianceStub, DeviceUpgradeStub]):
            final = await env.client.execute_workflow(
                NetworkComplianceOrchestrator.run, OrchestratorState(stop_after_cycles=1), id=wf_id(), task_queue="t")
            assert sorted(final.children_started) == ["d15-compliance-bos-acc-01", "d15-upgrade-nyc-rtr-01"]
            # ABANDON: children outlive the parent and finish on their own.
            child = await env.client.get_workflow_handle("d15-compliance-bos-acc-01").result()
            assert child.detail == "stub"
