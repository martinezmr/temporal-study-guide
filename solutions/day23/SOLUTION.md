# Day 23 — Solution

**Files:**

- `service.py`: contract plus `remediate`.
- `handler.py`: `@nexus.workflow_run_operation` starts Day 17's `ConfigComplianceWorkflow` in the compliance namespace.
- `workflows.py`: caller with `start_operation`, which awaits the result or cancels.

```bash
uv run python -m solutions.day23.run setup
uv run python -m solutions.day23.run demo bos-acc-01
uv run pytest solutions/tests/test_day22_24.py
```

## What you see in the UI

- **Caller** (`default`): `NexusOperationScheduled` → `NexusOperationStarted` → `NexusOperationCompleted`.
- **Handler** (`compliance`): a normal `ConfigComplianceWorkflow` run (`d23-compliance-bos-acc-01`). The UI links the two in both directions.

## Break-it answers

- **Handler worker down:** the caller sits at `NexusOperationScheduled` (or `Started`). Nothing fails; the operation completes when the worker returns. Nexus retries the start request for you.
- **Cancel:** `handle.cancel()` asks the handler to cancel the backing workflow. `ConfigComplianceWorkflow` catches the `CancelledError`, runs its `abort_session` compensation, and re-raises. The caller then sees the operation as cancelled.
- **Cancellation types:** the default `WAIT_COMPLETED` waits for the backing workflow to finish cancelling, which you want here so the rollback is done before the caller moves on. `TRY_CANCEL` returns immediately; `ABANDON` doesn't even ask.
