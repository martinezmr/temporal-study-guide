import pytest
from temporalio.client import WorkflowFailureError
from temporalio.exceptions import ActivityError, ApplicationError

from solutions.day03.workflows import FactsRequest, GetFactsV2Workflow
from solutions.shared import mock_lab
from solutions.tests.helpers import time_skipping_env, wf_id, worker


async def test_auth_failure_is_not_retried():
    mock_lab.fail_next("bos-rtr-01", 1, kind="auth")
    async with await time_skipping_env() as env:
        async with worker(env, "t", [GetFactsV2Workflow]):
            with pytest.raises(WorkflowFailureError) as e:
                await env.client.execute_workflow(
                    GetFactsV2Workflow.run, FactsRequest(device="bos-rtr-01"), id=wf_id(), task_queue="t")
    assert isinstance(e.value.cause, ActivityError)
    assert isinstance(e.value.cause.cause, ApplicationError)
    assert e.value.cause.cause.type == "AuthError"
    assert mock_lab.attempts("bos-rtr-01") == 1


async def test_timeouts_are_retried():
    mock_lab.fail_next("bos-rtr-01", 2)
    async with await time_skipping_env() as env:
        async with worker(env, "t", [GetFactsV2Workflow]):
            facts = await env.client.execute_workflow(
                GetFactsV2Workflow.run, FactsRequest(device="bos-rtr-01"), id=wf_id(), task_queue="t")
    assert facts.device == "bos-rtr-01"
    assert mock_lab.attempts("bos-rtr-01") == 3
