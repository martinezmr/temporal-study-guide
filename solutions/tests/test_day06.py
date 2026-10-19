from temporalio import activity
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from solutions.day02.workflows import GetFactsWorkflow
from solutions.shared.models import DeviceFacts
from solutions.tests.helpers import pydantic_data_converter, time_skipping_env, wf_id, worker


@activity.defn(name="get_device_facts")
async def fake_facts(device: str) -> DeviceFacts:
    return DeviceFacts(device=device, hostname=device, model="FakeEOS", version="9.9.9F")


async def test_mocked_activity():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [GetFactsWorkflow], activities=[fake_facts]):
            facts = await env.client.execute_workflow(GetFactsWorkflow.run, "bos-rtr-01", id=wf_id(), task_queue="t")
    assert facts.model == "FakeEOS"


async def test_history_json_round_trip_replays(tmp_path):
    async with await time_skipping_env() as env:
        async with worker(env, "t", [GetFactsWorkflow], activities=[fake_facts]):
            h = await env.client.start_workflow(GetFactsWorkflow.run, "bos-rtr-01", id=wf_id(), task_queue="t")
            await h.result()
            history = await h.fetch_history()
    path = tmp_path / "get_facts.json"
    path.write_text(history.to_json())  # same shape as `temporal workflow show -o json`
    loaded = WorkflowHistory.from_json("get_facts", path.read_text())
    await Replayer(workflows=[GetFactsWorkflow], data_converter=pydantic_data_converter).replay_workflow(loaded)
