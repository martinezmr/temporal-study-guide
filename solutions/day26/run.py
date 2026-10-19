"""Day 26.

    uv run python -m solutions.day26.run demo "Why can't bos-acc-01 reach bos-rtr-01?"
    (the demo shuts Ethernet1 on bos-acc-01 in the mock lab first)
    ANTHROPIC_API_KEY=... uv run python -m solutions.day26.run demo "..."
"""

import argparse

from solutions.day26.llm_step import llm_step
from solutions.day26.workflows import TASK_QUEUE, TroubleshootingAgentWorkflow
from solutions.shared import mock_lab
from solutions.shared.activities import DEVICE_ACTIVITIES
from solutions.day26.agent import AgentInput
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "demo"])
    p.add_argument("question", nargs="?", default="Why can't bos-acc-01 reach bos-rtr-01?")
    a = p.parse_args(argv)
    client = await connect()
    worker = make_worker(client, TASK_QUEUE, [TroubleshootingAgentWorkflow], [*DEVICE_ACTIVITIES, llm_step])
    if a.cmd == "worker":
        await worker.run()
        return
    mock_lab.shutdown_interface("bos-acc-01", "Ethernet1")
    async with worker:
        r = await client.execute_workflow(TroubleshootingAgentWorkflow.run, AgentInput(question=a.question),
                                          id="d26-troubleshoot", task_queue=TASK_QUEUE)
    print(f"{r.answer}\n\nturns={r.turns} tokens={r.tokens}\ntools: {r.tool_calls}")


if __name__ == "__main__":
    run(main)
