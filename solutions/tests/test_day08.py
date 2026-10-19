from solutions.day08.workflows import DeviceWatchWorkflow
from solutions.tests.eventually import eventually
from solutions.tests.helpers import time_skipping_env, wf_id, worker


async def test_pause_resume_and_stop():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [DeviceWatchWorkflow]):
            h = await env.client.start_workflow(DeviceWatchWorkflow.run, args=["bos-rtr-01", 300],
                                                id=wf_id(), task_queue="t")
            await eventually(lambda: h.query(DeviceWatchWorkflow.check_count), lambda n: n >= 1)
            await h.signal(DeviceWatchWorkflow.pause)
            assert await eventually(lambda: h.query(DeviceWatchWorkflow.is_paused))
            await h.signal(DeviceWatchWorkflow.resume)
            await h.signal(DeviceWatchWorkflow.force_check)
            await eventually(lambda: h.query(DeviceWatchWorkflow.check_count), lambda n: n >= 2)
            await h.signal(DeviceWatchWorkflow.stop)
            assert await h.result() >= 2
