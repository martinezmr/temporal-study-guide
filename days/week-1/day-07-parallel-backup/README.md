# Day 07 — Mini-project: parallel config backup + intent fetch

[← Day 06](../day-06-testing/README.md) · [Week 2 →](../../week-2/README.md)

## Goal

Your first real workflow: inventory from Nautobot, config from every device in parallel, and a report that survives partial failure.

## Understand it first

*About 3 minutes.*

Today combines the week into your first real workflow, and introduces the pattern you'll use most: **fan-out / fan-in**, doing the same thing to many devices at once and collecting the results.

**Parallelism in a workflow is just asyncio.** Workflow code runs on a special deterministic event loop, so the normal asyncio tools work:

```python
results = await asyncio.gather(
    *[workflow.execute_activity(get_running_config, d, ...) for d in devices],
    return_exceptions=True,
)
```

Each `execute_activity` call creates a command. Because nothing is awaited between them, all four commands go to the server in **one workflow task**: four `ActivityTaskScheduled` events, back to back, in history. Workers pick them up in parallel. The workflow wakes as each completes and continues once all have finished.

That's very different from a threaded script that SSHes to 4 devices. There are no threads in your code. The parallelism comes from the server handing out 4 tasks, and the workflow just waits for 4 results. Scale it to 400 devices and the workflow code doesn't change. You'd tune how many activities run at once on the worker side (Day 21).

**Partial failure is the normal case in networks.** With 4 devices something is usually fine; with 400, something is usually broken. Plain `asyncio.gather` raises on the first exception, which would fail the whole workflow and throw away 399 good backups. `return_exceptions=True` returns failures as values in the results list instead, so you can sort them into "saved" and "failed" and report both. The workflow **succeeds**, and its result says which devices need attention.

Pick consciously, every time you fan out: is one failure fatal for the whole operation, or is it a per-item outcome? For backups and audits it's per-item. For a coordinated change across a pair of devices (say, both ends of a link), one failure might mean "stop and roll back both".

**Each activity keeps its own retry policy.** The device that rejected auth fails fast (non-retryable). A device that timed out retries 3 times, and only then shows up as failed. You get per-device resilience without writing any per-device logic.

**Idempotent writes.** `save_backups` writes `backups/<device>.cfg`. If the worker dies after writing but before reporting success, Temporal runs it again, and it writes the same files. Same result, no harm. Compare a naive "append to backups.log" activity, which would duplicate lines on retry. Designing every activity so a retry is harmless is a habit worth building now.

**The source of truth enters the picture.** `list_devices` and `get_intended_config` read from Nautobot. That's the first half of the orchestrator's core loop:

```
intent  (Nautobot: what should be)   ─┐
                                      ├─▶ diff ─▶ drift report ─▶ (Week 3: remediate)
state   (devices: what is)           ─┘
```

Today you build both inputs. Week 2 builds the loop that compares them forever.

**Where to keep intent.** The solution reads it from Nautobot **config contexts** (a JSON blob per device or per role/site, merged by Nautobot): `target_version` plus `required_lines`. It's simple and good enough for the lab. Golden Config's intended configs are the production-grade version of the same idea.

**Checkpoint thinking:** before moving on, open this workflow's history and walk it top to bottom. You should be able to point at the fan-out (several `ActivityTaskScheduled` in one task), the out-of-order completions, the failed device's attempts, and the final save. If you can, Week 1 has done its job.

## Build

1. `activities/nautobot.py`: `list_devices() -> list[str]` via Nautobot GraphQL (`/api/graphql/`, token from `.env`).
2. `activities/eapi.py`: `get_running_config(device) -> DeviceState` (`show running-config` with `"format": "text"`, plus version).
3. `workflows/backup.py`:

    ```python
    @workflow.defn
    class BackupConfigsWorkflow:
        @workflow.run
        async def run(self) -> BackupReport:
            devices = await workflow.execute_activity(list_devices, start_to_close_timeout=timedelta(seconds=30))
            results = await asyncio.gather(
                *[workflow.execute_activity(get_running_config, d,
                      start_to_close_timeout=timedelta(seconds=60),
                      retry_policy=RetryPolicy(maximum_attempts=3)) for d in devices],
                return_exceptions=True,
            )
            ok = [r for r in results if isinstance(r, DeviceState)]
            failed = [d for d, r in zip(devices, results) if isinstance(r, BaseException)]
            await workflow.execute_activity(save_backups, ok, start_to_close_timeout=timedelta(seconds=30))
            return BackupReport(saved=[s.device for s in ok], failed=failed)
    ```

4. `save_backups` writes to `backups/<device>.cfg` (gitignored) — idempotent by design.

## Stretch

`get_intended_config(device) -> DeviceIntent` that reads intent from Nautobot (config context, or Golden Config intended config). Week 2 diffs this against state.

## Break it

Stop one node. The report should list 3 saved, 1 failed, and the workflow should **succeed**.

## Done when

- [ ] You can explain every event in this workflow's history, including the parallel `ActivityTaskScheduled` events.
- [ ] Tests cover the partial-failure case with mocks.
- [ ] One line in `LEARNING.md` for each day this week.

## Solution

Try it yourself first, then compare: [solutions/day07](../../../solutions/day07/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
