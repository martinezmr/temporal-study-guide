"""Day 28.

    uv run python -m solutions.day28.run demo "Is anything down on nyc-rtr-01?"
"""

import argparse

from solutions.day26.agent import AgentInput
from solutions.day26.llm_step import llm_step
from solutions.day28.workflows import TASK_QUEUE, GuardedTroubleshootingWorkflow
from solutions.shared.activities import DEVICE_ACTIVITIES
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "demo"])
    p.add_argument("question", nargs="?", default="Is anything down on nyc-rtr-01?")
    p.add_argument("--max-turns", type=int, default=6)
    p.add_argument("--budget", type=int, default=40_000)
    a = p.parse_args(argv)
    client = await connect()
    worker = make_worker(client, TASK_QUEUE, [GuardedTroubleshootingWorkflow], [*DEVICE_ACTIVITIES, llm_step])
    if a.cmd == "worker":
        await worker.run()
        return
    async with worker:
        r = await client.execute_workflow(
            GuardedTroubleshootingWorkflow.run, AgentInput(question=a.question, max_turns=a.max_turns,
                                                           token_budget=a.budget),
            id="d28-guarded", task_queue=TASK_QUEUE)
    print(f"{r.answer}\nstopped_by={r.stopped_by} turns={r.turns} tokens={r.tokens}\ntools: {r.tool_calls}")


if __name__ == "__main__":
    run(main)
