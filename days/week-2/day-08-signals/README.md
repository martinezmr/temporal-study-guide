# Day 08 — Signals

[← Week 1](../../week-1/README.md) · [Day 09 →](../day-09-queries/README.md)

## Goal

A workflow that loops forever and changes behaviour when you tell it to.

## Understand it first

*About 3 minutes.*

Until now your workflows were like batch jobs: start, run, finish. This week they become **long-lived services** that you talk to while they run. That's the foundation of the orchestrator, which runs forever and takes commands like "pause" and "check now".

There are three ways to talk to a running workflow: **signals** (today), **queries** (Day 9) and **updates** (Day 10).

**A signal is a one-way message into a workflow.** The sender says "deliver `force_check` to workflow `watch-bos-rtr-01`" and returns as soon as the server has **recorded** it. It doesn't wait for the workflow to act, and it gets nothing back. Think of it as a syslog message rather than an RPC call.

```python
@workflow.signal
def pause(self) -> None:
    self.paused = True
```

**Signals are events in history.** When you send one, the server writes `WorkflowExecutionSignaled` (with its payload) into the history and schedules a workflow task. The worker runs the handler, which changes some state, then the main code continues. Because the signal is in history, replay re-applies it at the same point, so the workflow's state rebuilds exactly. It's also why a signal sent while every worker is down isn't lost: it waits in history.

**The core pattern: handlers flip state, the main loop reacts.** Keep handlers tiny. They set flags or append to lists. The workflow's main loop waits on those changes with `workflow.wait_condition()`:

```python
await workflow.wait_condition(lambda: not self.paused)
```

`wait_condition` re-evaluates the lambda every time the workflow wakes up (a signal arrived, a timer fired, an activity completed) and returns when it's true. Add a `timeout=` and it becomes "wait for this OR for N seconds, whichever comes first", the workhorse of every polling loop you'll write:

```python
try:
    await workflow.wait_condition(lambda: self.check_requested, timeout=timedelta(minutes=5))
except TimeoutError:
    pass   # normal: 5 minutes passed, do the regular check
```

That's the whole design of a "check every 5 minutes, or immediately if asked" loop. No cron, no threads: one durable timer racing one flag.

**Why not do the work inside the handler?** You can await activities in an async signal handler, but then several handlers might run at once, interleaving with the main loop and with each other. Keeping work in one place, the main loop, makes behaviour easy to reason about and gives you natural ordering. Day 13 makes this explicit with a request queue.

**Signals are ordered and durable, but not acknowledged.** Two signals from one client arrive in the order sent. But the sender doesn't know whether the workflow *accepted* the signal, only that it was recorded. If the workflow is paused, a `force_check` just sets a flag that will matter later. If you need a yes/no answer or a result, use an update (Day 10).

**Signal-with-start.** Often you want "send this signal to the watch for bos-rtr-01, and start that watch if it doesn't exist". `client.start_workflow(..., start_signal="force_check")` does both atomically. You'll lean on that (and its update equivalent) when you build entity workflows.

**About `while True`.** Today's loop runs forever, and every iteration adds events to history. That's fine for a few days, but history has limits. Day 12 introduces Continue-As-New, which keeps a forever-workflow's history short. For now, notice the history growing as you watch.

**What you'll practise today:** sending signals from the CLI and from Python, sending one while the worker is down, and seeing that pause, resume and force-check change behaviour without restarting anything.

## Learn

- `@workflow.signal` methods mutate workflow state. They return nothing.
- `await workflow.wait_condition(lambda: ...)` blocks until state makes the lambda true — the main tool for reacting to signals.
- Signals sent while no worker is running are stored in history and delivered later.

## Build

```python
@workflow.defn
class DeviceWatchWorkflow:
    def __init__(self) -> None:
        self.paused = False
        self.check_requested = False
        self.checks = 0

    @workflow.run
    async def run(self, device: str) -> None:
        while True:
            await workflow.wait_condition(lambda: not self.paused)
            await workflow.execute_activity(get_device_facts, device,
                                            start_to_close_timeout=timedelta(seconds=30))
            self.checks += 1
            self.check_requested = False
            try:
                await workflow.wait_condition(lambda: self.check_requested,
                                              timeout=timedelta(minutes=5))
            except asyncio.TimeoutError:
                pass  # normal: 5 minutes passed

    @workflow.signal
    def pause(self) -> None:
        self.paused = True

    @workflow.signal
    def resume(self) -> None:
        self.paused = False

    @workflow.signal
    def force_check(self) -> None:
        self.check_requested = True
```

Starter: `handle = client.get_workflow_handle("watch-bos-rtr-01"); await handle.signal(DeviceWatchWorkflow.pause)`.

## Break it

- `temporal workflow signal --workflow-id watch-bos-rtr-01 --name pause`
- Stop the worker, send `force_check`, start the worker. The signal is waiting in history.
- Don't worry that `while True` grows history forever — Day 12 fixes it.

## Done when

- [ ] You can pause, resume and force a check from both the CLI and Python.

## Solution

Try it yourself first, then compare: [solutions/day08](../../../solutions/day08/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
