from solutions.day02.workflows import GetFactsWorkflow
from solutions.shared import mock_lab
from solutions.tests.helpers import time_skipping_env, wf_id, worker


async def test_facts_survive_transient_failures():
    mock_lab.fail_next("bos-rtr-01", 3)
    async with await time_skipping_env() as env:
        async with worker(env, "t", [GetFactsWorkflow]):
            facts = await env.client.execute_workflow(GetFactsWorkflow.run, "bos-rtr-01", id=wf_id(), task_queue="t")
    assert facts.version == "4.32.0F"
    assert mock_lab.attempts("bos-rtr-01") == 4
