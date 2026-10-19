"""Day 27.

    uv run python -m solutions.day27.run worker
    uv run python -m solutions.day27.run start bos-acc-01
    uv run python -m solutions.day27.run show bos-acc-01                 # reasoning + REAL device diff
    uv run python -m solutions.day27.run decide bos-acc-01 approve manny
    uv run python -m solutions.day27.run decide bos-acc-01 reject manny "not during freeze"
"""

import argparse

from temporalio.client import WorkflowUpdateFailedError

from solutions.day27.activities import propose_remediation
from solutions.day27.workflows import TASK_QUEUE, Decision, ProposalInput, ProposedRemediationWorkflow
from solutions.shared.activities import DEVICE_ACTIVITIES
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "start", "show", "decide"])
    p.add_argument("device", nargs="?", default="bos-acc-01")
    p.add_argument("verdict", nargs="?", choices=["approve", "reject"])
    p.add_argument("approver", nargs="?", default="manny")
    p.add_argument("comment", nargs="?", default="")
    a = p.parse_args(argv)

    client = await connect()
    wf_id = f"d27-proposal-{a.device}"
    if a.cmd == "worker":
        await make_worker(client, TASK_QUEUE, [ProposedRemediationWorkflow], [*DEVICE_ACTIVITIES, propose_remediation]).run()
    elif a.cmd == "start":
        await client.start_workflow(ProposedRemediationWorkflow.run, ProposalInput(device=a.device), id=wf_id,
                                    task_queue=TASK_QUEUE)
        print(f"started {wf_id}")
    elif a.cmd == "show":
        print((await client.get_workflow_handle(wf_id).query(ProposedRemediationWorkflow.get_proposal))
              .model_dump_json(indent=2))
    else:
        h = client.get_workflow_handle(wf_id)
        try:
            print(await h.execute_update(ProposedRemediationWorkflow.decide,
                                         Decision(approved=a.verdict == "approve", approver=a.approver, comment=a.comment)))
            print((await h.result()).model_dump_json(indent=2))
        except WorkflowUpdateFailedError as e:
            print(f"rejected by validator: {e.cause}")


if __name__ == "__main__":
    run(main)
