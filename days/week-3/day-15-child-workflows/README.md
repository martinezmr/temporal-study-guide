# Day 15 — Child workflows and parent close policy

[← Week 2](../../week-2/README.md) · [Day 16 →](../day-16-fan-out/README.md)

## Goal

The orchestrator starts a remediation workflow per drifted device.

## Understand it first

*About 3 minutes.*

The orchestrator can now see drift. To fix it, it needs to launch work that may take minutes (a config push) or hours (an upgrade that waits for a window). **Child workflows** let one workflow start others and, optionally, wait for their results.

**What a child workflow is.** A full workflow, with its own ID, its own history and its own retries and timeouts, started *by* another workflow instead of by a client:

```python
handle = await workflow.start_child_workflow(DeviceUpgradeWorkflow.run, inp, id="upgrade-nyc-rtr-01")
```

The parent's history records `StartChildWorkflowExecutionInitiated` → `ChildWorkflowExecutionStarted` and, if it waits, `ChildWorkflowExecutionCompleted` with the result. The UI links parent and child both ways.

**Why use a child instead of just more activities in the parent?**

- **Separate history.** An upgrade has dozens of events. Putting them all in the orchestrator's history would bloat it. A child keeps the parent's history to a few events per remediation.
- **Its own lifecycle.** A child can be queried, signalled, cancelled, retried or reset on its own. You can look at `upgrade-nyc-rtr-01` in the UI and see exactly where it is.
- **Separation of concerns.** The orchestrator decides *what* to fix; `ConfigComplianceWorkflow` knows *how*. Each can be tested and versioned on its own.
- **Different task queues or teams**, if needed. (For crossing namespaces and team boundaries, Nexus, in Week 4, is the better tool.)

**`execute_child_workflow` vs `start_child_workflow`.** `execute_…` starts the child and waits for its result: simple, but the parent is stuck until the child finishes. `start_…` returns a handle once the child has started, and the parent keeps going and can `await handle` later. The orchestrator must keep looping (checking other devices, answering queries) while an upgrade waits for 02:00, so it uses `start_…`.

**Parent close policy: what happens to children when the parent's run ends.** "Ends" includes completing, failing, being terminated **and continuing-as-new**:

| Policy | Effect on a running child |
| --- | --- |
| `TERMINATE` (default) | Killed instantly. No cleanup runs |
| `REQUEST_CANCEL` | Sent a cancellation; it can run its compensation and stop |
| `ABANDON` | Left alone; keeps running independently |

Combine the default with Day 12 and you get the trap: the orchestrator continues-as-new every N cycles, and with `TERMINATE` that would kill any upgrade or config push in progress, potentially leaving a router half-configured. For anything that touches devices, use **`ABANDON`**, and give the child its own safety (Day 17's rollback). It should be able to finish, or clean up after itself, no matter what happens to the parent.

**Child workflow IDs matter.** Give children deterministic, meaningful IDs: `compliance-bos-acc-01`, not a random UUID. You can find them in the UI, and because only one workflow per ID can run at a time, a deterministic ID is the first line of defence against duplicate remediations. Tomorrow builds on that.

**Errors propagate, if you wait.** If the parent awaits a child that fails, the parent gets a `ChildWorkflowError` wrapping the cause, just like `ActivityError` for activities. If the parent never awaits (fire-and-forget with `ABANDON`), it won't know how the child ended unless the child reports back. That gap is exactly what Day 16 closes.

**Today's deliberate shortcut:** the children are stubs that just sleep, and the parent remembers every child it ever started in a list. That's enough to see the mechanics: the parent starts children, the children outlive the parent, and the policies behave as described. Tomorrow replaces the list with proper dedup and a concurrency cap.

**What you'll practise today:** starting children from the orchestrator, finding them in the UI, and forcing a continue-as-new to compare `TERMINATE` with `ABANDON`.

## Learn

- `workflow.execute_child_workflow(...)` — start and wait for the result.
- `workflow.start_child_workflow(...)` — get a handle, keep looping, await it later.
- Children have their own history (good: the orchestrator's stays small) and their own ID.
- `ParentClosePolicy`: `TERMINATE` (default), `REQUEST_CANCEL`, `ABANDON` — what happens to the child when the parent run ends, **including on continue-as-new**.
- Docs: [Child workflows](https://docs.temporal.io/develop/python/workflows/child-workflows)

## Build

1. Stubs: `ConfigComplianceWorkflow(ComplianceInput)` and `DeviceUpgradeWorkflow(UpgradeInput)` that log and sleep 30 s.
2. In the orchestrator, after computing drift:

    ```python
    for report in drifted:
        if report.version_drift:
            await workflow.start_child_workflow(
                DeviceUpgradeWorkflow.run, UpgradeInput(device=report.device, ...),
                id=f"upgrade-{report.device}",
                parent_close_policy=ParentClosePolicy.ABANDON,
            )
        elif report.config_diff:
            await workflow.start_child_workflow(
                ConfigComplianceWorkflow.run, ComplianceInput(device=report.device, diff=report.config_diff),
                id=f"compliance-{report.device}",
                parent_close_policy=ParentClosePolicy.ABANDON,
            )
    ```

## Why ABANDON

The orchestrator continues-as-new regularly. With the default `TERMINATE`, every continue-as-new would kill a half-finished upgrade. Never do that to a router.

## Break it

Force a continue-as-new while a child is running (set the loop count low). With `TERMINATE` the child dies; with `ABANDON` it finishes.

## Done when

- [ ] Drift on a device produces a visible child in the UI, linked from the parent's history.

## Solution

Try it yourself first, then compare: [solutions/day15](../../../solutions/day15/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
