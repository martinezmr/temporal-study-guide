import pytest
from temporalio.worker import Replayer
from temporalio.workflow import NondeterminismError

from solutions.day04.workflows import QuietHoursInput, QuietHoursReordered, QuietHoursWorkflow
from solutions.tests.helpers import pydantic_data_converter, time_skipping_env, wf_id, worker


async def _history():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [QuietHoursWorkflow]):
            h = await env.client.start_workflow(
                QuietHoursWorkflow.run, QuietHoursInput(device="bos-rtr-01"), id=wf_id(), task_queue="t")
            await h.result()
            return await h.fetch_history()


async def test_same_code_replays():
    history = await _history()
    await Replayer(workflows=[QuietHoursWorkflow], data_converter=pydantic_data_converter).replay_workflow(history)


async def test_reordered_code_is_nondeterministic():
    history = await _history()
    with pytest.raises(NondeterminismError):
        await Replayer(workflows=[QuietHoursReordered],
                       data_converter=pydantic_data_converter).replay_workflow(history)
