# Day 11 — Durable timers and maintenance windows

[← Day 10](../day-10-updates/README.md) · [Day 12 →](../day-12-continue-as-new/README.md)

## Goal

Wait hours or days inside a workflow, reliably, and wake early when something happens.

## Understand it first

*About 3 minutes.*

Network work is full of waiting: for a maintenance window, for a device to reboot, for a human to approve, for a commit timer. In ordinary code, waiting hours is fragile. A process restart, a deploy or a laptop going to sleep loses the wait. In Temporal, **waiting is a first-class, durable operation**, and it costs nothing while it waits.

**`workflow.sleep()` creates a server-side timer.**

```python
await workflow.sleep(timedelta(hours=8))
```

Under the hood, the workflow sends a "start timer" command. The server records `TimerStarted` with the fire time, and the workflow is evicted from memory: no thread or process is held for 8 hours. When the timer fires, the server records `TimerFired` and schedules a workflow task. Any worker, possibly running code deployed since, replays the history and continues after the `sleep`.

So you can stop every worker, restart the Temporal container (with persistence), redeploy, and the wait is still exactly on schedule. The UI shows it under **Pending** with its fire time.

**Racing a timer against an event.** Real waits usually have an escape hatch: "wait for the window, unless someone declares an emergency". That's `wait_condition` with a timeout, which you met on Day 8:

```python
try:
    await workflow.wait_condition(lambda: self.emergency_override, timeout=window - now)
    return "override"
except TimeoutError:
    return "window"
```

The same shape covers "wait for approval for up to 4 hours" (Day 27) and "wait for the device to come back for up to 10 minutes" (Day 29). It's worth knowing by heart.

**Time inside a workflow comes from `workflow.now()`.** It returns the timestamp recorded for the current workflow task, so it's the same on replay. Compute windows from it, never from `datetime.now()`. It's UTC; converting to a site's local time needs a timezone. A fixed offset is fine for the lab. In production, look up each site's IANA zone (from Nautobot) and handle daylight saving, either in an activity or with `zoneinfo` passed through the sandbox.

**Timers vs schedules vs activity retries.** Three things in Temporal involve time, and they're easy to confuse:

| | Used for | Lives in |
| --- | --- | --- |
| **Timer** (`sleep`, `wait_condition` timeout) | A wait *inside* a workflow's logic | The workflow's history |
| **Retry backoff** | The gap between activity attempts | The activity's retry policy |
| **Schedule** (Day 18) | Starting a *new* workflow on a calendar | A server-side schedule object |

**Testing time.** Nobody can wait until 02:00 to see whether a test passes. The time-skipping test environment notices when the only thing left to do is wait for a timer, and jumps the clock straight to it. Your 22-hour wait completes in milliseconds, and the result reports exactly how many minutes of workflow time passed. That lets you assert "it waited about 20 hours" without waiting at all.

**Long timers and code changes.** A workflow sleeping for a day is replayed by whatever code is deployed when it wakes. If you changed what happens *before* the sleep, replay may not match history (Day 4). Long waits are where versioning (Day 19) earns its keep.

**What you'll practise today:** a maintenance-window helper with an override, restarting everything mid-wait to prove it survives, and two tests: one skipping ~20 hours of time, one proving the override wakes it early.

## Learn

- `await workflow.sleep(timedelta(days=3))` is a server-side timer: it survives worker restarts and deploys.
- `wait_condition(fn, timeout=...)` races a condition against a timer; it raises `asyncio.TimeoutError` on timeout.
- Docs: [Timers](https://docs.temporal.io/develop/python/workflows/timers)

## Build

```python
async def wait_for_maintenance_window(self, tz_offset_hours: int = -5) -> str:
    now = workflow.now() + timedelta(hours=tz_offset_hours)
    window = now.replace(hour=2, minute=0, second=0, microsecond=0)
    if window <= now:
        window += timedelta(days=1)
    try:
        await workflow.wait_condition(lambda: self.emergency_override,
                                      timeout=window - now)
        return "override"
    except asyncio.TimeoutError:
        return "window"
```

(Hard-coded offset is fine for the lab. Pass the device's site timezone from Nautobot later.)

Use it in the Day 10 maintenance flow: accept the request, wait for the window, run the activity.

## Test

```python
async with await WorkflowEnvironment.start_time_skipping() as env:
    ...
    result = await handle.result()   # 22 hours of waiting finishes in milliseconds
```

Then a second test that sends `emergency_override` and asserts the result is `"override"`.

## Break it

Start a workflow waiting for the window. Restart the worker *and* the Temporal container. The timer is still in the UI with the right fire time.

## Done when

- [ ] Both timer tests pass in under a second.

## Solution

Try it yourself first, then compare: [solutions/day11](../../../solutions/day11/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
