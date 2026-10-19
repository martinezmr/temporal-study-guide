# Day 18 — Schedules

[← Day 17](../day-17-saga-rollback/README.md) · [Day 19 →](../day-19-versioning/README.md)

## Goal

A nightly full audit that you can pause, trigger and backfill from the UI.

## Understand it first

*About 3 minutes.*

You've used timers inside workflows for recurring work. Temporal also has **Schedules**: server-side objects that start a *new* workflow on a calendar. Knowing which to use is a design decision you'll make repeatedly.

**What a Schedule is.** A named object on the server with three parts:

- **Spec:** when to run (cron expressions, intervals, calendar specs, a time zone, start and end dates, jitter).
- **Action:** what to do, which is "start workflow type X with input Y on task queue Z".
- **Policy:** how to behave when runs overlap or are missed.

```python
await client.create_schedule("nightly-compliance-audit", Schedule(
    action=ScheduleActionStartWorkflow(FullComplianceAuditWorkflow.run, id="full-audit", task_queue=...),
    spec=ScheduleSpec(cron_expressions=["0 1 * * *"], time_zone_name="America/Chicago"),
    policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP)))
```

Every time it fires, the server starts a fresh workflow run, appending a timestamp to the workflow ID so runs never collide.

**Why it beats cron:**

| | cron on a box | Temporal Schedule |
| --- | --- | --- |
| Visible | Log files somewhere | In the UI: next run times, recent runs with links |
| Pause for a change freeze | Edit crontab, remember to revert | `pause` with a note, `unpause` later |
| Missed runs (box was down) | Lost | Catch-up policy; `backfill` a time range on demand |
| Overlap (last run still going) | Two copies run | `SKIP`, `BUFFER_ONE`, `CANCEL_OTHER`, `ALLOW_ALL`… |
| Run now | SSH in, run the script | `trigger` |
| Each run's details | Whatever the script logged | A full workflow history |

**Timer loop or Schedule? The question is state.**

- The **orchestrator** carries state between iterations: what's in flight, what's queued, the latest drift. It needs to react to `force_check` and `set_interval` instantly. That's a timer loop inside one long-lived workflow.
- The **nightly full audit** carries nothing between nights. Each run starts from scratch, does its job and finishes. That's a Schedule.

Rule of thumb: **stateful and reactive → timer loop; stateless and calendar-driven → Schedule.**

**Overlap policies, in network terms.** If last night's audit is somehow still running at 01:00 (a device hanging, say), `SKIP` means "don't start another". That's almost always right for audits and backups. `BUFFER_ONE` queues exactly one run for when the current one finishes. `CANCEL_OTHER` stops the old run and starts fresh. Pick deliberately; the default is `SKIP`.

**Time zones and DST.** Give the spec `time_zone_name="America/Chicago"` and "01:00" means 01:00 local, year-round, with the server handling daylight saving. Without it, cron expressions are UTC and you'd have to adjust twice a year.

**Backfill.** Suppose the audit was paused during a freeze and you want the record filled in afterwards. `backfill` runs the action for every scheduled time in a past range, subject to the overlap policy you choose for the backfill. It's handy for reports, rarely needed for remediation.

**Schedules and versioning.** Each scheduled run is a new, short workflow, so it always runs on whatever code is current. That makes scheduled workflows the easiest kind to evolve. The long-lived orchestrator is the hard one, which is tomorrow's topic.

**What you'll practise today:** a stateless audit workflow, a nightly schedule in Central time, and every schedule operation (trigger, pause with a note, unpause, backfill, describe, delete) from both Python and the CLI.

## Learn

- Schedules replace cron: visible in the UI, pausable, with overlap policies and backfill.
- Stateful loop (the orchestrator) → a timer. Stateless periodic job (full audit) → a schedule.
- Docs: [Schedules](https://docs.temporal.io/develop/python/workflows/schedules)

## Build

`FullComplianceAuditWorkflow` — every device, every check, writes a report. Then:

```python
await client.create_schedule(
    "nightly-compliance-audit",
    Schedule(
        action=ScheduleActionStartWorkflow(
            FullComplianceAuditWorkflow.run, id="full-audit", task_queue=ORCHESTRATION_TASK_QUEUE),
        spec=ScheduleSpec(cron_expressions=["0 6 * * *"]),   # 01:00 Central = 06:00 UTC (CDT shifts it)
        policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
    ),
)
```

Or set `time_zone_name="America/Chicago"` on the spec to stop doing UTC math.

## CLI

```bash
temporal schedule list
temporal schedule trigger --schedule-id nightly-compliance-audit
temporal schedule toggle  --schedule-id nightly-compliance-audit --pause --reason "change freeze"
temporal schedule backfill --schedule-id nightly-compliance-audit \
  --start-time 2026-10-01T00:00:00Z --end-time 2026-10-03T00:00:00Z
```

## Done when

- [ ] The schedule shows in the UI with its next run time, and a manual trigger works.

## Solution

Try it yourself first, then compare: [solutions/day18](../../../solutions/day18/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
