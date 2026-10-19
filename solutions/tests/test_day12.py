from solutions.day12.workflows import DeviceWatchWorkflow, WatchInput
from solutions.tests.helpers import time_skipping_env, wf_id, worker


async def test_state_survives_continue_as_new():
    inp = WatchInput(device="bos-rtr-01", interval_seconds=60, max_loops_per_run=2, stop_after_checks=5)
    async with await time_skipping_env() as env:
        async with worker(env, "t", [DeviceWatchWorkflow]):
            final = await env.client.execute_workflow(DeviceWatchWorkflow.run, inp, id=wf_id(), task_queue="t")
    assert final.checks == 5
    assert final.runs == 3  # 2 + 2 + 1 checks
    assert final.last_facts.device == "bos-rtr-01"
