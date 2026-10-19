# Day 12 — Continue-As-New

[← Day 11](../day-11-timers/README.md) · [Day 13 →](../day-13-entity-workflows/README.md)

## Goal

A workflow that can run forever without its history growing forever.

## Understand it first

*About 3 minutes.*

Your watch workflow loops forever, and every loop adds events: an activity scheduled, started and completed, a timer started and fired. Left alone, its history grows without bound. **Continue-As-New** is how a forever-workflow stays healthy.

**Why history size matters.** Each workflow's history is capped, at roughly 51,200 events or 50 MB, after which the server terminates it. Long before that, big histories hurt: every time a worker needs to rebuild the workflow (cache eviction, restart, a query on a cold worker), it replays the **entire** history. A loop running every 15 minutes with 6 events per iteration gets about 600 events a day, so it would hit the limit in about 3 months and get slower to recover every day until then. The server warns at 10,240 events.

**What Continue-As-New does.** `workflow.continue_as_new(state)` atomically:

1. Completes the current **run** with the status `ContinuedAsNew`.
2. Starts a new run of the **same workflow type, same workflow ID**, with `state` as its input and an empty history.

```
Workflow ID: watch-bos-rtr-01
  Run 1  ── 100 checks ──▶ ContinuedAsNew(state)
  Run 2  ── 100 checks ──▶ ContinuedAsNew(state)
  Run 3  ── running …
```

To the outside world it's the same workflow. Signals, queries and updates sent to the workflow ID reach whichever run is current. `handle.result()` follows the chain to the final run. The UI shows the runs linked together.

**The rule that makes it work: all durable state goes through the input.** Anything not passed to `continue_as_new` is gone in the next run. The clean way to guarantee that is one pydantic model that is both the workflow's input and its state:

```python
class WatchInput(BaseModel):
    device: str
    checks: int = 0
    paused: bool = False
    last_facts: DeviceFacts | None = None

async def run(self, inp: WatchInput):
    self.s = inp
    ...
    workflow.continue_as_new(self.s)
```

Then there's no question of what carries over: the model is the state. Deliberately transient things, like a `check_requested` flag, live outside the model and reset each run.

**When to continue.** Two good triggers, used together:

- A **count you choose** ("every 100 loops"), which is predictable and easy to test.
- **`workflow.info().is_continue_as_new_suggested()`**, which the server sets when history is getting large. It's a safety net if your loop count is off.

**Don't drop in-flight messages.** If an update handler is mid-flight when the run ends, its caller gets an error. Before continuing, wait for handlers to finish:

```python
await workflow.wait_condition(workflow.all_handlers_finished)
workflow.continue_as_new(self.s)
```

Signals that arrive during the switchover are delivered to the new run, so they aren't lost.

**Continue-As-New is also a versioning tool.** Each new run starts fresh, so it's a natural point to move a long-lived workflow onto newly deployed code. Worker Versioning (Day 19) can upgrade a workflow exactly at its continue-as-new boundary. Keep that in mind for the orchestrator, which will run for months across many deploys.

**Children and continue-as-new.** A run ending affects its child workflows according to their parent close policy, the default being *terminate*. That's why Day 15 uses `ABANDON` for remediation children. Remember this pairing.

**What you'll practise today:** moving all state into one model, continuing every 3 loops, and watching run IDs change while the workflow ID, state and queries carry on seamlessly.

## Learn

- History is capped (about 51,200 events or 50 MB) and long histories make replay slow.
- `workflow.continue_as_new(state)` ends this run and starts a fresh one with the same workflow ID and the state you pass.
- `workflow.info().is_continue_as_new_suggested()` — the server tells you when it's time.
- Wait for in-flight signal/update handlers first: `await workflow.wait_condition(workflow.all_handlers_finished)`.
- Docs: [Continue-As-New](https://docs.temporal.io/develop/python/workflows/continue-as-new)

## Build

```python
class WatchInput(BaseModel):
    device: str
    checks: int = 0
    paused: bool = False
    last_facts: DeviceFacts | None = None

@workflow.run
async def run(self, inp: WatchInput) -> None:
    self.restore(inp)
    for _ in range(MAX_LOOPS_PER_RUN):          # 3 for today's experiment, ~100 later
        await self.one_cycle()
        if workflow.info().is_continue_as_new_suggested():
            break
    await workflow.wait_condition(workflow.all_handlers_finished)
    workflow.continue_as_new(self.snapshot())
```

## Break it

- Set `MAX_LOOPS_PER_RUN = 3`. Watch the chain of runs under one workflow ID in the UI (Run ID changes, Workflow ID doesn't).
- Query `get_status` across a continue-as-new boundary. State carries over.
- Send a signal right as it continues. It lands in the new run.

## Done when

- [ ] `DeviceWatchWorkflow` takes a single input model and continues-as-new safely.

## Solution

Try it yourself first, then compare: [solutions/day12](../../../solutions/day12/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
