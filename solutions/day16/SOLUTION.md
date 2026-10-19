# Day 16 — Solution

**Files:** `workflows.py` (orchestrator v2: `pending` queue, `in_flight` map, `max_concurrent=2`), `children.py` (children signal `remediation_finished` back to the parent).

```bash
uv run python -m solutions.day16.run worker --drift-all
uv run python -m solutions.day16.run start
uv run python -m solutions.day16.run state
uv run pytest solutions/tests/test_day16.py
```

## How duplicates are prevented

1. **In the orchestrator's state:** a device in `in_flight` or `pending` is never queued again, however many cycles or `force_check`s see it drifted.
2. **Deterministic child IDs:** `d16-compliance-<device>`. Even if state were lost, starting a second child with that ID while one is running fails instead of duplicating.
3. **From outside clients** (a CLI, a webhook) use `id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING` with the same IDs to attach to the running remediation.

## How the cap works

`_dispatch()` starts children only while `len(in_flight) < max_concurrent`. When a child signals `remediation_finished`, the handler frees the slot and sets `slot_freed`. That wakes the main loop **before** the next 15-minute cycle, so the queue drains as fast as slots open.

## Continue-As-New safety

`in_flight` and `pending` are in `OrchestratorState`, so they survive continue-as-new. Children signal the parent by **Workflow ID without a Run ID**, so the signal reaches whichever run is current.
