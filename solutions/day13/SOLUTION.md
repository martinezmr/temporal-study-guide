# Day 13 — Solution

**Files:** `workflows.py` → `DeviceEntityWorkflow`, `client.py` → `submit_to_device()` (update-with-start), `run.py burst` (fires many requests at once).

```bash
uv run python -m solutions.day13.run worker
uv run python -m solutions.day13.run burst bos-rtr-01 --count 10
uv run pytest solutions/tests/test_day13.py
```

## Why this prevents conflicting changes

Temporal allows **one running workflow per Workflow ID**. With ID `device-bos-rtr-01`, every request for that device lands in the same workflow. The workflow pulls requests off its queue one at a time and awaits each activity before starting the next. Two operators submitting at the same moment get serialized, not interleaved. In history, each request's activities finish before the next request's start.

## The shape

- **Handlers stay tiny:** `submit` appends to the queue and waits for its result. All real work happens in the main loop.
- **Idle → Continue-As-New:** after `idle_minutes` with nothing to do, the run continues as new with only `DeviceEntityInput`. Pending requests are drained first because the loop only exits when the queue is empty or idle.
- **`asyncio.Lock`** is safe in workflows (it's deterministic). It isn't strictly needed here, since only the main loop runs activities, but it guards you if you later let handlers do work.

## Where the orchestrator fits

On Day 14 the orchestrator is itself an entity (`network-compliance-orchestrator`). By the capstone you could route all remediation through these per-device entities for a hard per-device lock.
