# Day 16 — Fan-out without duplicates

[← Day 15](../day-15-child-workflows/README.md) · [Day 17 →](../day-17-saga-rollback/README.md)

## Goal

Detecting the same drift twice never starts two remediations, and you never remediate more than N devices at once.

## Understand it first

*About 3 minutes.*

Automation that fixes things needs brakes. Today adds two of the most important ones: **never run two remediations for the same device**, and **never run more than N remediations at once**. Without them, one bad intent change in Nautobot could push config to every device simultaneously, or push it twice.

**Brake 1: deduplication.** The orchestrator sees drift every 15 minutes, and again on every `force_check`. A remediation might take longer than one cycle. Without care, each cycle would start another remediation for the same device. Three layers stop that:

1. **State in the orchestrator.** `in_flight` maps device → running child. `pending` is a queue of devices waiting for a slot. A device that's in either is never queued again.
2. **Deterministic child IDs.** `compliance-bos-acc-01`: even if the state were somehow wrong, Temporal refuses to start a second running workflow with the same ID.
3. **ID conflict policy for outside callers.** A CLI or webhook that triggers a remediation uses `id_conflict_policy=USE_EXISTING` with the same ID, and attaches to the running one instead of failing or duplicating.

There's also an **ID reuse policy**, which governs starting a new run when a *closed* workflow with that ID exists. The default allows it, which is what you want: after yesterday's remediation finished, today's drift can start a new one.

**Brake 2: a concurrency cap.** `max_concurrent = 2` means at most two devices are being changed at any time; the rest wait in `pending`. That limits the blast radius. If the remediation logic is wrong, you find out on two devices, not four hundred. Change management people call this a canary or a rolling change, and here it's a few lines of state.

**Knowing when a slot frees up: children report back.** Yesterday's fire-and-forget children didn't tell the parent when they finished. Today they **signal** the parent at the end:

```python
parent = workflow.info().parent
await workflow.get_external_workflow_handle(parent.workflow_id).signal("remediation_finished", done)
```

The parent's handler removes the device from `in_flight`, records the outcome, and sets `slot_freed`. The main loop is waiting on `check_requested or slot_freed` with a timeout until the next cycle, so it wakes **immediately** and starts the next pending device. The queue drains as fast as slots open, not once every 15 minutes.

Note the handle uses only the **workflow ID**, not a run ID. If the orchestrator continued-as-new while the child was running, the signal still reaches the current run, which carried `in_flight` across in its state. That's why the queue and map live in `OrchestratorState`.

**The scheduling loop.** The orchestrator now juggles two clocks, the detection cycle and remediation completions:

```
loop:
    if cycle due (timer passed or force_check): detect drift, enqueue new drifted devices
    dispatch: while pending and len(in_flight) < cap → start child
    wait until (force_check or slot freed), at most until the next cycle is due
```

It's a small event-driven scheduler, and because it's a workflow, it's durable. Crash the worker mid-dispatch and the history knows exactly which children were started.

**An alternative you'll see on Day 29:** instead of children signalling back, the orchestrator can start a small asyncio task per remediation that awaits the child's result. Both work. Signals survive continue-as-new more gracefully; awaiting is simpler to read. Knowing both helps you choose.

**What you'll practise today:** drift every device at once and watch exactly two remediations run, then the next two; spam `force_check` and confirm there's still exactly one child per device.

## Learn

- Deterministic IDs (`compliance-bos-rtr-01`) + ID conflict policy: if a run with that ID is already open, `WorkflowIDConflictPolicy.USE_EXISTING` attaches instead of failing or duplicating. (From the orchestrator, simplest is to track open children in state; from outside clients, use the policy.)
- Children can report back to the parent with a signal: `workflow.get_external_workflow_handle(parent_id).signal(...)`.

## Build

1. Orchestrator state gets `in_flight: set[str]` and `pending: list[DriftReport]`.
2. Only start a child if the device isn't in `in_flight`, and only while `len(in_flight) < MAX_CONCURRENT_REMEDIATIONS` (2).
3. Children signal `remediation_finished(device, result)` to the parent (`workflow.info().parent.workflow_id`); the handler removes it from `in_flight`, and the loop starts the next pending one.
4. Carry `in_flight` and `pending` through continue-as-new.

## Break it

- Drift all 4 devices at once. Watch exactly 2 children run, then the next 2.
- Hit `force_check` 5 times quickly. Still one child per device.

## Done when

- [ ] Tests cover the concurrency cap and the no-duplicate rule.

## Solution

Try it yourself first, then compare: [solutions/day16](../../../solutions/day16/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
