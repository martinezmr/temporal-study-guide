# Day 04 — Solution

**Files:** `workflows.py` has three workflows:

- `QuietHoursWorkflow` uses every replay-safe API: `workflow.now()`, `workflow.uuid4()`, `workflow.random()`, `workflow.logger`, `workflow.sleep()`.
- `QuietHoursReordered` is the "bad deploy": same type name, activities swapped.
- `BrokenClockWorkflow` calls `datetime.now()` so you can see the sandbox stop it.

```bash
uv run python -m solutions.day04.run demo bos-rtr-01
uv run pytest solutions/tests/test_day04.py      # proves the reordered code can't replay old histories
```

## Three things that must never happen in workflow code

1. **Non-deterministic calls:** `datetime.now()`, `random`, `uuid.uuid4()`, reading env vars or files. Use the `workflow.*` equivalents, or move the work into an activity.
2. **I/O:** network, disk, subprocess. Activities only.
3. **Changing the order or kind of commands** (activities, timers, children, signals sent) for histories that already exist. On replay, the worker compares the commands your code produces with the recorded events. A mismatch is a `NondeterminismError`.

## What you saw in the break-it exercise

The worker replays the history (`ActivityTaskScheduled: get_device_facts`), but the new code asks for `get_lldp` first. The SDK raises a non-determinism error and **fails the workflow task, not the workflow**. The task retries forever, waiting for a fixed worker. Retrying won't help. The fixes are versioning (Day 19), resetting the workflow, or terminating it.

## The sandbox

`BrokenClockWorkflow` fails with `RestrictedWorkflowAccessError` before it can do damage. The sandbox re-imports modules per workflow run and intercepts known non-deterministic calls. `workflow.unsafe.imports_passed_through()` lets your activity and model modules be imported once and shared, which is faster and safe because they hold no workflow state.
