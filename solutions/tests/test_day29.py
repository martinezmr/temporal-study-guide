from solutions.day17.workflows import ConfigComplianceWorkflow
from solutions.day25.activities import explain_drift
from solutions.day27.activities import propose_remediation
from solutions.day27.workflows import ProposedRemediationWorkflow
from solutions.day29.upgrade import DeviceUpgradeWorkflow
from solutions.day29.workflows import NetworkComplianceOrchestrator, OrchestratorState
from solutions.shared import mock_lab
from solutions.shared.activities import DEVICE_ACTIVITIES
from solutions.tests.helpers import time_skipping_env, wf_id, worker

WORKFLOWS = [NetworkComplianceOrchestrator, DeviceUpgradeWorkflow, ProposedRemediationWorkflow, ConfigComplianceWorkflow]
ACTIVITIES = [*DEVICE_ACTIVITIES, explain_drift, propose_remediation]


def _state(**kw) -> OrchestratorState:
    return OrchestratorState(stop_after_cycles=1, use_nexus=False, skip_windows=True, **kw)


async def test_end_to_end_default_drift():
    async with await time_skipping_env() as env:
        async with worker(env, "t", WORKFLOWS, ACTIVITIES):
            final = await env.client.execute_workflow(NetworkComplianceOrchestrator.run, _state(), id=wf_id(),
                                                      task_queue="t")
    outcomes = {o.device: o for o in final.completed}
    assert outcomes["bos-acc-01"].path == "child" and outcomes["bos-acc-01"].status == "remediated"
    assert outcomes["nyc-rtr-01"].path == "upgrade" and outcomes["nyc-rtr-01"].status == "upgraded"
    assert "ntp server 10.0.0.1" in mock_lab.config_of("bos-acc-01")
    assert final.explanations["bos-acc-01"].risk == "low"


async def test_medium_risk_goes_to_approval_and_times_out_safely():
    mock_lab.remove_line("nyc-acc-01", "aaa authorization exec default local")
    before = mock_lab.config_of("nyc-acc-01")
    async with await time_skipping_env() as env:
        async with worker(env, "t", WORKFLOWS, ACTIVITIES):
            final = await env.client.execute_workflow(NetworkComplianceOrchestrator.run, _state(max_concurrent=3),
                                                      id=wf_id(), task_queue="t")
    outcome = next(o for o in final.completed if o.device == "nyc-acc-01")
    assert outcome.path == "approval" and outcome.status == "timed-out"
    assert mock_lab.config_of("nyc-acc-01") == before
