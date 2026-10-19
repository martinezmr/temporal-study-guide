"""Day 18.

    uv run python -m solutions.day18.run worker
    uv run python -m solutions.day18.run create          # 01:00 America/Chicago, nightly
    uv run python -m solutions.day18.run trigger         # run one now
    uv run python -m solutions.day18.run pause "change freeze"
    uv run python -m solutions.day18.run unpause
    uv run python -m solutions.day18.run backfill 3      # catch up the last 3 days
    uv run python -m solutions.day18.run describe
    uv run python -m solutions.day18.run delete
"""

import argparse
from datetime import datetime, timedelta, timezone

from temporalio.client import (
    Schedule, ScheduleActionStartWorkflow, ScheduleBackfill, ScheduleOverlapPolicy, SchedulePolicy, ScheduleSpec,
)

from solutions.day18.workflows import SCHEDULE_ID, TASK_QUEUE, FullComplianceAuditWorkflow
from solutions.shared.activities import DEVICE_ACTIVITIES
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "create", "trigger", "pause", "unpause", "backfill", "describe", "delete"])
    p.add_argument("arg", nargs="?")
    a = p.parse_args(argv)

    client = await connect()
    handle = client.get_schedule_handle(SCHEDULE_ID)
    if a.cmd == "worker":
        await make_worker(client, TASK_QUEUE, [FullComplianceAuditWorkflow], DEVICE_ACTIVITIES).run()
    elif a.cmd == "create":
        await client.create_schedule(
            SCHEDULE_ID,
            Schedule(
                action=ScheduleActionStartWorkflow(FullComplianceAuditWorkflow.run, id="d18-full-audit",
                                                   task_queue=TASK_QUEUE),
                spec=ScheduleSpec(cron_expressions=["0 1 * * *"], time_zone_name="America/Chicago"),
                policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
            ),
        )
        print(f"created {SCHEDULE_ID}")
    elif a.cmd == "trigger":
        await handle.trigger()
    elif a.cmd == "pause":
        await handle.pause(note=a.arg or "paused from CLI")
    elif a.cmd == "unpause":
        await handle.unpause()
    elif a.cmd == "backfill":
        end = datetime.now(timezone.utc)
        await handle.backfill(ScheduleBackfill(start_at=end - timedelta(days=int(a.arg or 1)), end_at=end,
                                               overlap=ScheduleOverlapPolicy.ALLOW_ALL))
    elif a.cmd == "describe":
        d = await handle.describe()
        print(f"paused={d.schedule.state.paused} next={d.info.next_action_times[:3]} recent={len(d.info.recent_actions)}")
    else:
        await handle.delete()


if __name__ == "__main__":
    run(main)
