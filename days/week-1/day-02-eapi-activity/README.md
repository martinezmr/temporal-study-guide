# Day 02 — First real activity: facts over eAPI

[← Day 01](../day-01-lab-up/README.md) · [Day 03 →](../day-03-models-and-failures/README.md)

## Goal

A workflow that gets `show version` from a cEOS node, and survives the node going away.

## Understand it first

*About 3 minutes.*

Today your activity talks to a real switch, so it needs to cope with the real world: devices reboot, links flap, eAPI is slow while the CPU is busy. Temporal gives you two tools for that, **timeouts** and **retries**, and choosing them well is most of what makes an activity production-grade.

**Timeouts answer "how long is too long?"** There are four, and they measure different things:

| Timeout | Measures | Network analogy |
| --- | --- | --- |
| **Start-to-close** | One attempt, from a worker picking it up to finishing | Per-packet timeout |
| **Schedule-to-close** | The whole thing, all attempts and waits included | Overall session deadline |
| **Schedule-to-start** | Time sitting in the queue before any worker picks it up | Queueing delay |
| **Heartbeat** | Max silence from a long-running attempt (Day 5) | Keepalive / dead-peer detection |

You must set start-to-close or schedule-to-close; most people set start-to-close. Think about what one attempt should take. A `show version` over eAPI finishes in well under a second, so 30 seconds is generous and still catches a hung TCP session. Without a timeout, a hung connection could stall forever.

Schedule-to-start is rarely set, because a task waiting in the queue usually just means no worker is running, and when you start one it gets processed. It's useful when stale work is worse than no work.

**Retries answer "what do we do after a failure?"** Every activity has a retry policy, and the default retries **forever** with exponential backoff: 1 s, 2 s, 4 s … capped at 100 s between attempts. That surprises people, but it's a sensible default for "this must eventually happen" work like saving a backup. For a health check you usually want a bounded answer, so today you set:

```python
RetryPolicy(initial_interval=2s, backoff_coefficient=2.0, maximum_interval=30s, maximum_attempts=5)
```

That gives attempts at roughly 0, 2, 6, 14 and 30 seconds, then failure.

**Retries are invisible to the workflow.** This is the key mental shift. Your workflow code says `await execute_activity(get_device_facts, ...)` and gets back facts. It doesn't know or care whether that took one attempt or four; the server handled the retries. You don't write retry loops in workflow code, ever. If all attempts fail, the `await` raises `ActivityError`, and only then does the workflow have to decide what to do.

**The server tracks attempts, not your worker.** The retry timer lives on the server, so you can kill every worker mid-retry, start one an hour later, and the next attempt happens then. In the UI, a retrying activity shows under **Pending Activities** with its attempt number, last failure and next retry time. That view will be your best friend when a device is down.

**Activities must be safe to run more than once.** An attempt can do its work and then fail to report back: the worker died, or the network dropped the response. Temporal will run it again. For a `show` command that's harmless. For a config push it matters a lot, and it's why Day 17 uses config sessions, where re-applying the same session is a no-op. Get into the habit now of asking for every activity: what happens if this runs twice?

**About the mock.** Starting today, write device access behind a small function that can be swapped for a fake (`DEVICE_MODE=mock`). Your tests will use it, and it lets you study without the lab running. The solution's `shared/mock_lab.py` is a fuller version of the same idea.

**What to watch for in the break-it exercise:** stop a node and read the activity's pending state. The attempt count climbs and the backoff grows. Start the node before the last attempt and the workflow finishes as if nothing happened. That moment, recovery with zero code, is the point of this whole tool.

## Learn

- Four activity timeouts: **start-to-close** (one attempt), **schedule-to-close** (all attempts), **schedule-to-start** (waiting in queue), **heartbeat** (Day 5). Always set start-to-close.
- The default retry policy retries forever with exponential backoff. Decide your own.
- Docs: [Activity timeouts](https://docs.temporal.io/develop/python/activities/timeouts) · [Activity execution](https://docs.temporal.io/develop/python/activities/execution)

## Build

1. `activities/eapi.py`: a small async eAPI client (niquests, JSON-RPC `runCmds`) and an activity:

    ```python
    @activity.defn
    async def get_device_facts(device: str) -> dict:
        host = DEVICE_HOSTS[device]
        result = await run_commands(host, ["show version"])
        v = result[0]
        return {"device": device, "model": v["modelName"], "version": v["version"]}
    ```

2. `workflows/facts.py`: `GetFactsWorkflow` calling it with:

    ```python
    await workflow.execute_activity(
        get_device_facts, device,
        start_to_close_timeout=timedelta(seconds=30),
        retry_policy=RetryPolicy(initial_interval=timedelta(seconds=2),
                                 backoff_coefficient=2.0, maximum_attempts=5),
    )
    ```

3. Register both in `workers/main.py`; add `starters/facts.py`.
4. Start the habit now: `activities/eapi_mock.py` returning a canned `show version` from `tests/fixtures/`, chosen when `DEVICE_MODE=mock` ([why](../../../docs/codespaces.md)).

## Break it

- `docker/podman stop bos-rtr-01` (or `containerlab` stop that node) and start the workflow. Watch **Pending Activities** in the UI: attempt count, last failure, next retry.
- Start the node again before attempt 5. The workflow finishes with no code change.
- Let it exceed 5 attempts. Read how the failure is reported in the workflow result.

## Done when

- [ ] Facts come back for all 4 devices (one workflow each).
- [ ] You can explain the difference between the activity failing and the workflow failing.

## Solution

Try it yourself first, then compare: [solutions/day02](../../../solutions/day02/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
