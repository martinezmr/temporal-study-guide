# Day 10 — Solution

**Files:** `workflows.py`. The `request_maintenance` update waits until the main loop has run the task, then returns a ticket. Its validator rejects the wrong device, a paused watch, or a duplicate ID. `run.py maint` uses **update-with-start**.

```bash
uv run python -m solutions.day10.run worker
uv run python -m solutions.day10.run maint bos-rtr-01 clear-counters
uv run python -m solutions.day10.run maint bos-rtr-01 clear-counters --wrong
uv run pytest solutions/tests/test_day10.py     # uses a local dev server (downloaded once)
```

## Signal or update for a network change request?

| | Signal | Update |
| --- | --- | --- |
| Caller learns the result | No (fire-and-forget) | Yes, waits for the return value |
| Can be rejected up front | No, it's always recorded | Yes: the validator runs first, and a rejection is never written to history |
| Good for | "check now", "pause", "stop" | "do this change and tell me the outcome", approvals |

A change request should be an **update**: the operator (or CI job) needs the outcome, and invalid requests shouldn't pollute the audit trail.

## Update-with-start

`WithStartWorkflowOperation(..., id_conflict_policy=USE_EXISTING)` + `execute_update_with_start_workflow` means "send this to the workflow for device X, starting it first if it isn't running", in one atomic call. Signal-with-start is the fire-and-forget version (`client.start_workflow(..., start_signal="force_check")`).

## Why `all_handlers_finished` before returning

If `stop` arrives while an update is waiting, returning immediately would leave that caller with an error. Waiting for handlers to finish lets in-flight updates complete first. Day 12 uses the same idea before Continue-As-New.
