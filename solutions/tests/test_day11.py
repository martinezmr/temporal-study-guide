from solutions.day11.workflows import MaintenanceWindowWorkflow, WindowInput
from solutions.tests.helpers import time_skipping_env, wf_id, worker


async def test_waits_for_window():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [MaintenanceWindowWorkflow], activities=[]):
            r = await env.client.execute_workflow(MaintenanceWindowWorkflow.run, WindowInput(device="bos-rtr-01"),
                                                  id=wf_id(), task_queue="t")
    assert r.reason == "window"
    assert 0 < r.waited_minutes <= 24 * 60


async def test_override_wakes_early():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [MaintenanceWindowWorkflow], activities=[]):
            h = await env.client.start_workflow(MaintenanceWindowWorkflow.run, WindowInput(device="bos-rtr-01"),
                                                id=wf_id(), task_queue="t")
            await h.signal(MaintenanceWindowWorkflow.override)
            r = await h.result()
    assert r.reason == "override"
