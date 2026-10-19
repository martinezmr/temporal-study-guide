from solutions.day29.workflows import NetworkComplianceOrchestrator, OrchestratorState
from solutions.day29.workers import ALL_ACTIVITIES, CAPSTONE_WORKFLOWS
from solutions.day30.replay_histories import replay_dir
from solutions.tests.helpers import time_skipping_env, wf_id, worker


async def test_replay_gate_passes_on_fresh_capstone_history(tmp_path):
    async with await time_skipping_env() as env:
        async with worker(env, "t", CAPSTONE_WORKFLOWS, ALL_ACTIVITIES):
            h = await env.client.start_workflow(
                NetworkComplianceOrchestrator.run,
                OrchestratorState(stop_after_cycles=1, use_nexus=False, skip_windows=True),
                id=wf_id("orch"), task_queue="t")
            await h.result()
            (tmp_path / "orchestrator.json").write_text((await h.fetch_history()).to_json())
    assert await replay_dir(str(tmp_path)) == []
