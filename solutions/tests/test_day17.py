import pytest
from temporalio.client import WorkflowFailureError

from solutions.day17.workflows import ConfigComplianceWorkflow
from solutions.shared import mock_lab
from solutions.shared.models import ComplianceInput
from solutions.tests.helpers import time_skipping_env, wf_id, worker


async def test_remediation_applies_and_confirms():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [ConfigComplianceWorkflow]):
            r = await env.client.execute_workflow(
                ConfigComplianceWorkflow.run, ComplianceInput(device="bos-acc-01", missing_lines=["ntp server 10.0.0.1"]),
                id=wf_id(), task_queue="t")
    assert r.applied and r.diff == ["+ntp server 10.0.0.1"]
    assert "ntp server 10.0.0.1" in mock_lab.config_of("bos-acc-01")


async def test_failed_verification_rolls_back():
    before = mock_lab.config_of("bos-acc-01")
    async with await time_skipping_env() as env:
        async with worker(env, "t", [ConfigComplianceWorkflow]):
            with pytest.raises(WorkflowFailureError):
                await env.client.execute_workflow(
                    ConfigComplianceWorkflow.run,
                    ComplianceInput(device="bos-acc-01", missing_lines=["ntp server 10.0.0.1"], force_verify_failure=True),
                    id=wf_id(), task_queue="t")
    assert mock_lab.config_of("bos-acc-01") == before


async def test_already_compliant_does_nothing():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [ConfigComplianceWorkflow]):
            r = await env.client.execute_workflow(
                ConfigComplianceWorkflow.run, ComplianceInput(device="bos-rtr-01", missing_lines=["ntp server 10.0.0.1"]),
                id=wf_id(), task_queue="t")
    assert not r.applied and r.detail == "already compliant"
