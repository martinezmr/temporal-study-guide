# Day 05 — Blocking libraries, heartbeats, cancellation

[← Day 04](../day-04-determinism/README.md) · [Day 06 →](../day-06-testing/README.md)

## Goal

Use blocking network libraries safely, and make long activities resumable.

## Understand it first

*About 3 minutes.*

Two practical problems today: using network libraries that **block**, and activities that run **long enough that you need to know they're still alive**.

**How the Python worker runs activities.** The worker is an asyncio program. `async def` activities run on its event loop alongside everything else the worker does: polling for tasks, sending heartbeats, running workflow code. That's efficient as long as every `async def` activity actually `await`s its I/O. niquests' `AsyncSession` does.

Most network automation libraries don't. pyeapi, netmiko, napalm and paramiko make **blocking** calls. Inside an `async def`, a blocking call freezes the whole event loop for its duration: no polling, no heartbeats, every other activity stalled. With one slow switch, your worker looks dead to the server.

**The fix: sync activities in a thread pool.** Declare the activity as a plain `def` and give the worker an executor:

```python
@activity.defn
def get_lldp_neighbors(device: str) -> list[dict]:   # plain def → runs in a thread
    ...
Worker(..., activity_executor=ThreadPoolExecutor(max_workers=10))
```

The SDK runs each sync activity on a pool thread, so the event loop stays free. The pool size caps how many blocking activities run at once on this worker. That's a natural throttle for SSH sessions.

Rule of thumb: an async library goes in `async def`; a blocking library goes in `def` with an executor. Never mix them.

**Heartbeats: proving you're alive.** A `show tech-support` or a firmware copy can take minutes. Start-to-close alone is a blunt tool: set it to 10 minutes and a worker that died at minute 1 isn't noticed until minute 10. A **heartbeat** is a periodic "still working" ping from the activity to the server:

```python
activity.heartbeat(progress)        # call this regularly
execute_activity(..., heartbeat_timeout=timedelta(seconds=15))
```

If no heartbeat arrives for 15 seconds, the server declares the attempt dead and schedules a retry right away, without waiting out the start-to-close timeout. It's dead-peer detection for activities.

**Heartbeat details make work resumable.** The value you pass to `heartbeat()` is saved by the server. When the next attempt starts, it reads `activity.info().heartbeat_details` and can skip what's done. For a 10-command show tech, "I finished command 6" means the retry starts at command 7. For a firmware copy, it could be a byte offset. (Heartbeats are throttled, so not every call reaches the server instantly. Treat details as "at least this much is done".)

**Heartbeats also carry cancellation.** Activities don't get interrupted mid-instruction. They learn they've been cancelled when they heartbeat:

- In an `async def` activity, the next `await` raises `asyncio.CancelledError`.
- In a `def` activity, `activity.is_cancelled()` starts returning `True`, so check it between steps.

An activity that never heartbeats can't be cancelled promptly. It runs to completion or until its timeout. So: **long activity ⇒ heartbeat_timeout + regular heartbeats**, always.

**Why this matters later.** Your device-io workers will run many blocking calls against many switches. Thread pools give you a per-worker concurrency limit; Day 21 adds a server-side rate limit across all workers. Upgrades (Day 29) include long waits and checks where heartbeats and resumability matter.

**Break-it goal for today:** kill the worker in the middle of the show tech, restart it, and watch the next attempt pick up exactly where the heartbeat left off.

## Learn

- `async def` activities must never block the event loop. Blocking libraries (pyeapi, netmiko, napalm) go in **sync** activities with an `activity_executor`.
- **Heartbeat**: a long activity reports progress with `activity.heartbeat(details)`. If heartbeats stop for `heartbeat_timeout`, the attempt is failed and retried, and the next attempt reads `activity.info().heartbeat_details`.
- Heartbeats are also how an activity learns it was **cancelled**.
- Docs: [Sync vs async](https://docs.temporal.io/develop/python/best-practices/python-sdk-sync-vs-async) · [Cancellation](https://docs.temporal.io/develop/python/workflows/cancellation)

## Build

1. A sync activity with a blocking library:

    ```python
    @activity.defn
    def get_lldp_neighbors(device: str) -> list[dict]:
        node = pyeapi.connect(host=DEVICE_HOSTS[device], username=..., password=..., transport="https")
        return node.execute(["show lldp neighbors"])["result"][0]["lldpNeighbors"]
    ```

    Worker: `Worker(..., activity_executor=ThreadPoolExecutor(max_workers=10))`.

2. `collect_show_tech(device)` that runs 10 slow commands one by one, heartbeating after each:

    ```python
    start = activity.info().heartbeat_details[0] if activity.info().heartbeat_details else 0
    for i, cmd in enumerate(COMMANDS[start:], start=start):
        output.append(run(cmd))
        activity.heartbeat(i + 1)
    ```

    Call it with `heartbeat_timeout=timedelta(seconds=15)`.

## Break it

- Kill the worker during `collect_show_tech`. Restart it. The next attempt resumes at the last heartbeat, not at command 1.
- Cancel the workflow from the UI during the activity. Catch `asyncio.CancelledError` (async) or check `activity.is_cancelled()` (sync) and clean up.

## Done when

- [ ] You know which of your activities are async vs sync and why.
- [ ] You've watched a heartbeat timeout fire and an attempt resume.

## Solution

Try it yourself first, then compare: [solutions/day05](../../../solutions/day05/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
