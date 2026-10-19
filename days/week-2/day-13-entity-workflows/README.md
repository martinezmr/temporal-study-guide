# Day 13 — The entity workflow pattern

[← Day 12](../day-12-continue-as-new/README.md) · [Day 14 →](../day-14-orchestrator-v0/README.md)

## Goal

One long-lived workflow per device that is the single owner of that device's changes.

## Understand it first

*About 3 minutes.*

The **entity workflow** is one of the most useful Temporal patterns, and it maps naturally onto networks: **one long-lived workflow per real-world thing**, with the thing's name as the workflow ID. For you, that means one workflow per device (`device-bos-rtr-01`) and, tomorrow, one for the whole compliance system (`network-compliance-orchestrator`).

**Why it works: the ID uniqueness guarantee.** Temporal allows at most one running workflow per workflow ID in a namespace. So if every request to change `bos-rtr-01` goes through the workflow with ID `device-bos-rtr-01`, you get:

- **A per-device lock for free.** Two operators, a CI job and the orchestrator can all send changes at the same moment. They land in the same workflow, which processes them one at a time.
- **A single owner of state.** The device's in-flight work, recent results and queue all live in one place you can query.
- **No external locking service.** No Redis lock or database row to forget to release when a script crashes.

**The anatomy of an entity workflow:**

```
callers ──update-with-start──▶  submit(req) handler: append to queue, wait for result
                                       │
                               main loop: wait for queue → pop → run activities → store result
                                       │
                               idle for an hour, or history large → continue-as-new(state)
```

1. **Handlers are thin.** `submit` appends the request to `self.queue` and waits until its result appears. No device work happens in the handler.
2. **The main loop is the only place work happens.** It waits for the queue to be non-empty, pops one request, runs its activities to completion, records the result, and repeats. Serialization falls out of that structure: one loop, one request at a time.
3. **Callers always use update-with-start** (Day 10) with `USE_EXISTING`. They never ask whether the entity exists. If it does, they reuse it; if not, they start it.
4. **It continues-as-new** when idle or when history grows (Day 12), carrying only durable state.

**Concurrency inside a workflow.** Workflow code is single-threaded and deterministic, but async handlers can interleave at `await` points. In the pattern above only the main loop awaits activities, so there's no interleaving to worry about. If you ever let handlers do work too, use `asyncio.Lock()` (safe in workflows) to protect critical sections.

**Choosing what is an entity.** Good candidates have a stable identity, a lifecycle, and benefit from serialized access:

| Entity | Workflow ID | Why |
| --- | --- | --- |
| A device | `device-<hostname>` | Never two conflicting changes at once |
| A site rollout | `rollout-<site>-<change>` | Tracks progress across many devices |
| The compliance system | `network-compliance-orchestrator` | One brain deciding what to remediate |

Things that are just jobs, like "back up configs" or "run tonight's audit", stay ordinary workflows.

**Entities and history.** An entity that runs for a year must continue-as-new, so its durable state must be small and explicit (Day 12). The idle timeout trick ("nothing to do for an hour, so roll over") keeps quiet entities tidy.

**How the orchestrator relates.** Tomorrow's orchestrator is an entity too: one decision-maker. On Day 29 it could route every change through per-device entities, giving you two levels of protection, one brain choosing what to fix and one gatekeeper per device deciding when. You don't need that in the lab, but it's how this scales.

**What you'll practise today:** a device entity with a request queue, a client that always uses update-with-start, and a burst of ten concurrent requests. You'll see in history that their activities ran strictly one after another.

## Learn

- **Entity workflow:** the workflow ID *is* the thing's name (`device-bos-rtr-01`). Temporal guarantees one running workflow per ID, so you get a per-device lock for free.
- Requests arrive as signals/updates and are appended to a queue; the main loop drains it one at a time. Handlers stay tiny.
- Use `asyncio.Lock()` (safe in workflows) if two handlers might run activities at the same time.

## Build

`workflows/device_entity.py`:

```python
@workflow.defn
class DeviceEntityWorkflow:
    def __init__(self) -> None:
        self.queue: list[DeviceRequest] = []
        self.results: dict[str, RequestResult] = {}

    @workflow.run
    async def run(self, inp: DeviceEntityInput) -> None:
        self.restore(inp)
        while not workflow.info().is_continue_as_new_suggested():
            try:
                await workflow.wait_condition(lambda: bool(self.queue), timeout=timedelta(hours=1))
            except asyncio.TimeoutError:
                break  # idle for an hour: continue-as-new to keep history short
            req = self.queue.pop(0)
            self.results[req.id] = await self.handle(req)   # one at a time
        await workflow.wait_condition(workflow.all_handlers_finished)
        workflow.continue_as_new(self.snapshot())

    @workflow.update
    async def submit(self, req: DeviceRequest) -> RequestResult:
        self.queue.append(req)
        await workflow.wait_condition(lambda: req.id in self.results)
        return self.results.pop(req.id)
```

Callers always use update-with-start (Day 10), so they never care whether the entity is running.

## Break it

Fire 10 `submit` calls concurrently with `asyncio.gather` from a starter. Confirm in history that the activities run strictly one after another.

## Done when

- [ ] You can explain why two operators can't push conflicting changes to the same device with this design.

## Solution

Try it yourself first, then compare: [solutions/day13](../../../solutions/day13/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
