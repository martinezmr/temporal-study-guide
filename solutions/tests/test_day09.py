from solutions.day09.workflows import DeviceWatchWorkflow
from solutions.tests.eventually import eventually
from solutions.tests.helpers import time_skipping_env, wf_id, worker


async def test_status_query_reports_last_facts():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [DeviceWatchWorkflow]):
            h = await env.client.start_workflow(DeviceWatchWorkflow.run, args=["nyc-rtr-01", 300],
                                                id=wf_id(), task_queue="t")
            status = await eventually(lambda: h.query(DeviceWatchWorkflow.get_status), lambda s: s.checks >= 1)
            assert status.last_facts.version == "4.31.2F"
            assert status.last_checked is not None
            await h.signal(DeviceWatchWorkflow.stop)
            assert (await h.result()).device == "nyc-rtr-01"
