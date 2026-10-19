# Day 10 — Updates and validators

[← Day 09](../day-09-queries/README.md) · [Day 11 →](../day-11-timers/README.md)

## Goal

Send a request into a running workflow, get an answer back, and reject bad requests before they touch history.

## Understand it first

*About 3 minutes.*

Signals can't reply, and queries can't change anything. **Updates** do both: a request that changes workflow state **and** returns a result to the caller, with the option to reject invalid requests before anything is recorded. For network change requests, updates are usually the right tool.

**An update is a handler that can be async, can change state, and returns a value:**

```python
@workflow.update
async def request_maintenance(self, req: MaintenanceRequest) -> MaintenanceTicket:
    self.queue.append(req)
    await workflow.wait_condition(lambda: req.id in self.done)   # wait for the main loop to run it
    return self.done[req.id]
```

The caller uses `await handle.execute_update(...)` and **blocks until the handler returns**. That can be milliseconds or minutes. Here the ticket comes back only after the maintenance task has actually run. Compare that with a signal, where the caller would have to poll a query to find out what happened.

**Validators reject bad requests before they're recorded.**

```python
@request_maintenance.validator
def validate_maintenance(self, req: MaintenanceRequest) -> None:
    if req.device != self.device:
        raise ValueError("wrong device")
```

The validator runs first, read-only, like a query. If it raises, the caller gets `WorkflowUpdateFailedError` **and nothing is written to history**. Only accepted updates become events (`WorkflowExecutionUpdateAccepted`, then `...Completed`). That keeps your audit trail clean: a history of "changes requested and executed", not "every typo anyone sent".

Validators must not change state or await anything. Put checks in them, not work.

**Choosing between the three:**

| You want to… | Use |
| --- | --- |
| Nudge the workflow and move on ("check now", "pause") | **Signal** |
| Read state ("what's drifted?") | **Query** |
| Ask it to do something and get the outcome, rejecting invalid asks ("apply this change", "approve") | **Update** |

A change request should almost always be an update: the requester needs the result, and you want invalid requests rejected cleanly.

**Update-with-start: talk to a workflow whether or not it's running.** In the entity pattern (Day 13), there's one workflow per device, and callers shouldn't have to care whether the one for `bos-rtr-01` currently exists. Update-with-start sends "start this workflow if needed, then deliver this update" as one atomic call:

```python
op = WithStartWorkflowOperation(DeviceWatchWorkflow.run, "bos-rtr-01", id="watch-bos-rtr-01",
                                task_queue=..., id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING)
ticket = await client.execute_update_with_start_workflow(DeviceWatchWorkflow.request_maintenance, req,
                                                          start_workflow_operation=op)
```

`USE_EXISTING` means: if a workflow with that ID is already running, use it; otherwise start one. Signal-with-start is the fire-and-forget sibling.

**Workflow IDs are your keys.** Temporal guarantees at most one *running* workflow per workflow ID in a namespace. That's what makes the ID `watch-bos-rtr-01` meaningful: it's *the* watch for that device. You'll build a lot on this guarantee: deduplication on Day 16, per-device locking on Day 13.

**Finishing cleanly.** If the workflow returns while an update is still waiting, that update fails at the caller. That's why the solution ends with `await workflow.wait_condition(workflow.all_handlers_finished)` before returning: in-flight handlers complete first. You'll use the same line before every continue-as-new.

**What you'll practise today:** an update that waits for real work, a validator that rejects the wrong device without a trace in history, and update-with-start, run twice to prove it reuses the running workflow.

## Learn

- `@workflow.update` = signal + return value. The caller waits for the result.
- `@my_update.validator` runs first; raising rejects the update and **nothing is written to history**.
- **Update-with-start** / **signal-with-start**: "send this to the workflow for device X, starting it if it doesn't exist." The building block of entity workflows (Day 13).

## Build

```python
@workflow.update
async def request_maintenance(self, req: MaintenanceRequest) -> MaintenanceTicket:
    self.maintenance_queue.append(req)
    await workflow.wait_condition(lambda: req.id in self.accepted)
    return MaintenanceTicket(id=req.id, scheduled_for=self.accepted[req.id])

@request_maintenance.validator
def validate_maintenance(self, req: MaintenanceRequest) -> None:
    if req.device != self.device:
        raise ValueError(f"this workflow owns {self.device}, not {req.device}")
    if self.paused:
        raise ValueError("watch is paused")
```

Caller:

```python
ticket = await handle.execute_update(DeviceWatchWorkflow.request_maintenance, req)
```

Update-with-start:

```python
start_op = WithStartWorkflowOperation(
    DeviceWatchWorkflow.run, "bos-rtr-01",
    id="watch-bos-rtr-01", task_queue=ORCHESTRATION_TASK_QUEUE,
    id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
)
ticket = await client.execute_update_with_start_workflow(
    DeviceWatchWorkflow.request_maintenance, req, start_workflow_operation=start_op)
```

Signal-with-start is `client.start_workflow(..., start_signal="force_check")`.

## Break it

- Send an update for the wrong device. It fails at the caller, and the workflow's history has no trace of it.
- Run update-with-start twice. Second call reuses the running workflow.

## Done when

- [ ] You can explain when you'd pick a signal vs an update for a network change request.

## Solution

Try it yourself first, then compare: [solutions/day10](../../../solutions/day10/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
