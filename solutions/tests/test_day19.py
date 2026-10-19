import pytest
from temporalio.worker import Replayer
from temporalio.workflow import NondeterminismError

from solutions.day19.workflows import DeviceAuditV1, DeviceAuditV2, DeviceAuditV2Bad
from solutions.tests.helpers import pydantic_data_converter, time_skipping_env, wf_id, worker


async def _v1_history():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [DeviceAuditV1]):
            h = await env.client.start_workflow(DeviceAuditV1.run, "bos-rtr-01", id=wf_id(), task_queue="t")
            await h.result()
            return await h.fetch_history()


async def test_patched_v2_replays_v1_history():
    await Replayer(workflows=[DeviceAuditV2], data_converter=pydantic_data_converter).replay_workflow(await _v1_history())


async def test_unpatched_v2_breaks_v1_history():
    with pytest.raises(NondeterminismError):
        await Replayer(workflows=[DeviceAuditV2Bad],
                       data_converter=pydantic_data_converter).replay_workflow(await _v1_history())


async def test_new_runs_take_the_patched_branch():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [DeviceAuditV2]):
            r = await env.client.execute_workflow(DeviceAuditV2.run, "bos-rtr-01", id=wf_id(), task_queue="t")
    assert r.neighbors == 2
