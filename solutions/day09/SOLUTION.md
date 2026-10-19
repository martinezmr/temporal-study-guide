# Day 09 — Solution

**Files:** `workflows.py` → `get_status()` query returning a `WatchStatus` model; `run.py status` lists every running watch with `client.list_workflows(...)` and queries each one.

```bash
uv run python -m solutions.day09.run worker
uv run python -m solutions.day09.run start bos-rtr-01 bos-acc-01 nyc-rtr-01 nyc-acc-01
uv run python -m solutions.day09.run status
uv run pytest solutions/tests/test_day09.py
```

## Query rules

- No `await`, no activities, no timers, no state changes. A query runs against the in-memory workflow state, often by replaying history on a worker that doesn't have it cached.
- Queries are **not** recorded in history; signals and updates are.
- A worker must be running for the workflow's task queue, even for completed workflows.

## Visibility vs queries

`list_workflows` uses the server's visibility store (fast, indexed, eventually consistent). `query` asks the workflow itself (exact, needs a worker). Day 20 adds search attributes so that visibility can answer "which devices are drifted?" without querying each one.
