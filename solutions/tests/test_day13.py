import asyncio

from solutions.day13.client import submit_to_device
from solutions.day13.workflows import DeviceEntityWorkflow, DeviceRequest
from solutions.tests.helpers import local_env, worker


async def test_concurrent_requests_are_serialized():
    async with await local_env() as env:
        async with worker(env, "t", [DeviceEntityWorkflow]):
            reqs = [DeviceRequest(id=f"r{i}", action="facts" if i % 2 else "lldp") for i in range(5)]
            results = await asyncio.gather(*[submit_to_device(env.client, "bos-acc-01", r, task_queue="t") for r in reqs])
            await env.client.get_workflow_handle("device-bos-acc-01").terminate("test done")
    assert sorted(r.position for r in results) == [1, 2, 3, 4, 5]
