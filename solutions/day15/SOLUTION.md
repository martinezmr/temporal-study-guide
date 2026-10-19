# Day 15 — Solution

**Files:** `children.py` (stub child workflows), `workflows.py` (orchestrator v1 starts one child per drifted device), `../shared/drift_cycle.py` (Day 14's collection step, reused from here on).

```bash
uv run python -m solutions.day15.run worker
uv run python -m solutions.day15.run start
uv run pytest solutions/tests/test_day15.py
```

## execute vs start

- `execute_child_workflow` = start + await the result. The parent is blocked until the child finishes.
- `start_child_workflow` = start, return a handle. The parent keeps looping. **The orchestrator must never block on a 2-hour upgrade**, so it uses `start_child_workflow`.

## ParentClosePolicy

| Policy | What happens to the child when the parent run ends (including continue-as-new) |
| --- | --- |
| `TERMINATE` (default) | Killed immediately |
| `REQUEST_CANCEL` | Asked to cancel; can clean up |
| `ABANDON` | Keeps running on its own |

An upgrade or config push must never be killed halfway because the orchestrator rolled over its history, so both children use `ABANDON`.

## Known gap (fixed tomorrow)

`children_started` is a crude dedup: it never forgets a device, and nothing limits how many children run at once. Day 16 replaces it with `in_flight` + `pending` + a concurrency cap, and the children report back.
