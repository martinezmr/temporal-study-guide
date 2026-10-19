from solutions.day14.workflows import NetworkComplianceOrchestrator, OrchestratorState
from solutions.shared import mock_lab
from solutions.tests.eventually import eventually
from solutions.tests.helpers import time_skipping_env, wf_id, worker


async def test_detects_default_drift():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [NetworkComplianceOrchestrator]):
            final = await env.client.execute_workflow(
                NetworkComplianceOrchestrator.run, OrchestratorState(stop_after_cycles=1), id=wf_id(), task_queue="t")
    drifted = {r.device: r for r in final.reports if r.drifted}
    assert set(drifted) == {"bos-acc-01", "nyc-rtr-01"}
    assert drifted["bos-acc-01"].missing_lines == ["ntp server 10.0.0.1"]
    assert drifted["nyc-rtr-01"].version_drift


async def test_force_check_sees_fix():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [NetworkComplianceOrchestrator]):
            h = await env.client.start_workflow(NetworkComplianceOrchestrator.run,
                                                OrchestratorState(stop_after_cycles=2), id=wf_id(), task_queue="t")
            await eventually(lambda: h.query(NetworkComplianceOrchestrator.get_state), lambda s: s.cycle >= 1)
            assert len(await h.query(NetworkComplianceOrchestrator.get_drift)) == 2
            mock_lab.make_compliant()
            await h.signal(NetworkComplianceOrchestrator.force_check)
            final = await h.result()
    assert final.cycle == 2
    assert not [r for r in final.reports if r.drifted]
