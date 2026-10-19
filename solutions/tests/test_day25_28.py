from temporalio import activity
from temporalio.worker import Replayer

from solutions.day25.activities import explain_drift
from solutions.day25.workflows import ExplainDriftWorkflow
from solutions.day26.agent import AgentInput
from solutions.day26.llm_step import AgentTurnInput, AgentTurnOutput, llm_step
from solutions.day26.workflows import TroubleshootingAgentWorkflow
from solutions.day27.activities import propose_remediation
from solutions.day27.workflows import Decision, ProposalInput, ProposedRemediationWorkflow
from solutions.day28.workflows import GuardedTroubleshootingWorkflow
from solutions.shared import mock_lab
from solutions.shared.activities import DEVICE_ACTIVITIES
from solutions.tests.eventually import eventually
from solutions.tests.helpers import local_env, pydantic_data_converter, time_skipping_env, wf_id, worker


async def test_explain_drift_mock():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [ExplainDriftWorkflow], [*DEVICE_ACTIVITIES, explain_drift]):
            r = await env.client.execute_workflow(ExplainDriftWorkflow.run, "bos-acc-01", id=wf_id(), task_queue="t")
            none = await env.client.execute_workflow(ExplainDriftWorkflow.run, "bos-rtr-01", id=wf_id(), task_queue="t")
    assert r.risk == "low" and "ntp" in r.summary
    assert none is None


async def test_agent_finds_shut_interface():
    mock_lab.shutdown_interface("bos-acc-01", "Ethernet1")
    async with await time_skipping_env() as env:
        async with worker(env, "t", [TroubleshootingAgentWorkflow], [*DEVICE_ACTIVITIES, llm_step]):
            r = await env.client.execute_workflow(
                TroubleshootingAgentWorkflow.run, AgentInput(question="Why can't bos-acc-01 reach bos-rtr-01?"),
                id=wf_id(), task_queue="t")
    assert "Ethernet1 on bos-acc-01" in r.answer
    assert r.stopped_by == "answer" and r.turns == 3


async def test_agent_history_replays():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [TroubleshootingAgentWorkflow], [*DEVICE_ACTIVITIES, llm_step]):
            h = await env.client.start_workflow(TroubleshootingAgentWorkflow.run,
                                                AgentInput(question="Check nyc-rtr-01"), id=wf_id(), task_queue="t")
            await h.result()
            history = await h.fetch_history()
    await Replayer(workflows=[TroubleshootingAgentWorkflow],
                   data_converter=pydantic_data_converter).replay_workflow(history)


@activity.defn(name="llm_step")
async def stubborn_model(turn: AgentTurnInput) -> AgentTurnOutput:
    """A 'model' that keeps trying a forbidden command and never answers."""
    return AgentTurnOutput(
        content=[{"type": "tool_use", "id": f"t{len(turn.messages)}", "name": "run_show_command",
                  "input": {"device": "bos-rtr-01", "command": "configure terminal"}}],
        stop_reason="tool_use", input_tokens=100, output_tokens=10)


@activity.defn(name="llm_step")
async def expensive_model(turn: AgentTurnInput) -> AgentTurnOutput:
    return AgentTurnOutput(content=[{"type": "tool_use", "id": "t1", "name": "get_lldp", "input": {"device": "bos-rtr-01"}}],
                           stop_reason="tool_use", input_tokens=90_000, output_tokens=10)


async def test_guardrails_block_commands_and_cap_turns():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [GuardedTroubleshootingWorkflow], [*DEVICE_ACTIVITIES, stubborn_model]):
            r = await env.client.execute_workflow(GuardedTroubleshootingWorkflow.run,
                                                  AgentInput(question="hack it", max_turns=3), id=wf_id(), task_queue="t")
    assert r.stopped_by == "max_turns"
    assert not any(cmds for _, cmds in mock_lab.calls if "configure terminal" in cmds)


async def test_token_budget():
    async with await time_skipping_env() as env:
        async with worker(env, "t", [GuardedTroubleshootingWorkflow], [*DEVICE_ACTIVITIES, expensive_model]):
            r = await env.client.execute_workflow(GuardedTroubleshootingWorkflow.run,
                                                  AgentInput(question="x", token_budget=50_000), id=wf_id(), task_queue="t")
    assert r.stopped_by == "token_budget"


async def test_proposal_approved_applies_change():
    async with await local_env() as env:
        async with worker(env, "t", [ProposedRemediationWorkflow], [*DEVICE_ACTIVITIES, propose_remediation]):
            h = await env.client.start_workflow(ProposedRemediationWorkflow.run, ProposalInput(device="bos-acc-01"),
                                                id=wf_id(), task_queue="t")
            view = await eventually(lambda: h.query(ProposedRemediationWorkflow.get_proposal),
                                    lambda v: v.stage == "awaiting-approval")
            assert view.device_diff == ["+ntp server 10.0.0.1"]
            await h.execute_update(ProposedRemediationWorkflow.decide, Decision(approved=True, approver="manny"))
            outcome = await h.result()
    assert outcome.status == "applied" and outcome.approver == "manny"
    assert "ntp server 10.0.0.1" in mock_lab.config_of("bos-acc-01")


async def test_proposal_times_out_without_change():
    before = mock_lab.config_of("bos-acc-01")
    async with await time_skipping_env() as env:
        async with worker(env, "t", [ProposedRemediationWorkflow], [*DEVICE_ACTIVITIES, propose_remediation]):
            outcome = await env.client.execute_workflow(ProposedRemediationWorkflow.run,
                                                        ProposalInput(device="bos-acc-01"), id=wf_id(), task_queue="t")
    assert outcome.status == "timed-out"
    assert mock_lab.config_of("bos-acc-01") == before
