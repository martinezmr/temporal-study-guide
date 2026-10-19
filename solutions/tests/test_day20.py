from solutions.day20.search_attributes import ALL
from solutions.day20.workflows import ComplianceSweepWorkflow, DeviceComplianceCheckWorkflow
from solutions.tests.eventually import eventually
from solutions.tests.helpers import local_env, wf_id, worker


async def test_drifted_devices_are_searchable():
    async with await local_env(search_attributes=ALL) as env:
        async with worker(env, "t", [ComplianceSweepWorkflow, DeviceComplianceCheckWorkflow]):
            drifted = await env.client.execute_workflow(ComplianceSweepWorkflow.run, id=wf_id(), task_queue="t")
            assert drifted == ["bos-acc-01", "nyc-rtr-01"]

            async def bos_drifted():
                return [wf.id async for wf in env.client.list_workflows('ComplianceState="drifted" AND Site="bos"')]

            ids = await eventually(bos_drifted, lambda ids: len(ids) == 1)
            assert ids[0].startswith("d20-check-bos-acc-01")
