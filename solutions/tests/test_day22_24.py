"""Nexus tests need a real dev server with an endpoint, so they use local_env() (downloaded once).

Both 'teams' share the default namespace here to keep the test simple; the run.py demos use two namespaces.
"""

from solutions.day17.workflows import ConfigComplianceWorkflow
from solutions.day22.handler import ComplianceServiceHandler as Handler22
from solutions.day22.workflows import ENDPOINT as EP22
from solutions.day22.workflows import PolicyCallerWorkflow
from solutions.day24.handler import ComplianceServiceHandler as Handler24
from solutions.day24.workflows import ENDPOINT as EP24
from solutions.day24.workflows import RemediateWithPolicyWorkflow
from solutions.netops_contracts.compliance import ComplianceInput
from solutions.shared import mock_lab
from solutions.shared.nexus_setup import ensure_endpoint
from solutions.tests.helpers import local_env, wf_id, worker


async def test_sync_policy_operation():
    async with await local_env() as env:
        await ensure_endpoint(env.client, EP22, "default", "handler22")
        async with worker(env, "handler22", [], activities=[], nexus_service_handlers=[Handler22()]), \
                worker(env, "caller22", [PolicyCallerWorkflow], activities=[]):
            policy = await env.client.execute_workflow(PolicyCallerWorkflow.run, "access", id=wf_id(),
                                                       task_queue="caller22")
    assert "ntp server 10.0.0.1" in policy.required_lines


async def test_remediate_and_reject_via_nexus():
    async with await local_env() as env:
        await ensure_endpoint(env.client, EP24, "default", "handler24")
        async with worker(env, "handler24", [ConfigComplianceWorkflow], nexus_service_handlers=[Handler24()]), \
                worker(env, "caller24", [RemediateWithPolicyWorkflow], activities=[]):
            ok = await env.client.execute_workflow(
                RemediateWithPolicyWorkflow.run,
                ComplianceInput(device="bos-acc-01", missing_lines=["ntp server 10.0.0.1"]),
                id=wf_id(), task_queue="caller24")
            rejected = await env.client.execute_workflow(
                RemediateWithPolicyWorkflow.run, ComplianceInput(device="lab-sw-99", missing_lines=["x"]),
                id=wf_id(), task_queue="caller24")
    assert ok.status == "remediated"
    assert "ntp server 10.0.0.1" in mock_lab.config_of("bos-acc-01")
    assert rejected.status == "manual"
