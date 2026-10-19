# Day 22 — Solution

**Files:**

- `service.py`: the contract.
- `handler.py`: compliance team, sync operation.
- `workflows.py`: NetOps team, caller.
- `run.py`: endpoint setup plus both workers.
- `../shared/nexus_setup.py`: creates an endpoint from Python.

```bash
uv run python -m solutions.day22.run setup
uv run python -m solutions.day22.run demo access
uv run pytest solutions/tests/test_day22_24.py
```

The equivalent CLI for the endpoint:

```bash
temporal operator nexus endpoint create --name d22-compliance-endpoint \
  --target-namespace compliance --target-task-queue solutions-day22-compliance
temporal operator nexus endpoint list
```

## Who knows what

| | Caller (`default`) | Handler (`compliance`) |
| --- | --- | --- |
| Knows the contract (`service.py`) | ✔ | ✔ |
| Knows the endpoint name | ✔ | — |
| Knows the handler's namespace, task queue, code | ✘ | ✔ |

The endpoint maps the name to a namespace + task queue. The compliance team can move queues, rewrite the handler, or move to another namespace by re-pointing the endpoint, with no change to callers.

## Sync operations

`@nexusrpc.handler.sync_operation` returns within the request (Temporal enforces a short deadline, about 10 seconds). Use it for lookups. Anything long or durable is an async, workflow-backed operation (Day 23). Unknown roles raise `HandlerError(NOT_FOUND)`, which the caller receives as a non-retryable failure.

## History to look for

In `PolicyCallerWorkflow`: `NexusOperationScheduled` → `NexusOperationCompleted`. A sync operation has no `Started` event.
