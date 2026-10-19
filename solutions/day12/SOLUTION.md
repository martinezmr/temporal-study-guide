# Day 12 — Solution

**Files:** `workflows.py`. All durable state lives in one `WatchInput` model. That model is both the workflow's input and what it passes to `continue_as_new`.

```bash
uv run python -m solutions.day12.run worker
uv run python -m solutions.day12.run start bos-rtr-01 --loops 3 --interval 10
uv run python -m solutions.day12.run state bos-rtr-01
uv run pytest solutions/tests/test_day12.py
```

## The pattern

```python
self.s = inp; self.s.runs += 1
while not time_to_continue():
    ...one cycle...
await workflow.wait_condition(workflow.all_handlers_finished)
workflow.continue_as_new(self.s)
```

- **State in, state out.** Anything not in `WatchInput` is lost at the boundary. That includes `check_requested`, which is deliberately transient here.
- **When to continue:** a loop count you choose, or `is_continue_as_new_suggested()` (the server's hint, based on history size). Use both.
- **`all_handlers_finished`:** an update waiting on the old run would otherwise fail when the run ends.
- `client.execute_workflow` / `handle.result()` follow the chain of runs, so callers see the final result.

## What you see in the UI

One Workflow ID, several Run IDs. Each run ends with `WorkflowExecutionContinuedAsNew`, and the new run starts with the carried state as its input. Queries and signals sent to the Workflow ID always reach the current run.
