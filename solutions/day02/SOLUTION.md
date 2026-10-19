# Day 02 — Solution

**Files:** `workflows.py` (the workflow + retry policy), `../shared/eapi.py` (eAPI client), `../shared/activities.py` → `get_device_facts`, `../shared/mock_lab.py` (fake switches).

```bash
uv run python -m solutions.day02.run demo bos-rtr-01 nyc-rtr-01
uv run python -m solutions.day02.run demo bos-rtr-01 --fail 3     # watch retries in the UI
DEVICE_MODE=live uv run --env-file .env python -m solutions.day02.run demo bos-rtr-01
uv run pytest solutions/tests/test_day02.py
```

## Key decisions

- **start-to-close = 30 s** bounds one attempt. A hung HTTPS session can't stall the workflow forever.
- **Retry policy:** 2 s → 4 s → 8 s → 16 s, max 5 attempts. The default (retry forever) is right for many activities, but for "is this device up?" you want a bounded answer.
- **The pydantic converter is already on** (via `solutions/shared/runner.py`). Day 3 explains it; using it from day 2 keeps every later day consistent.

## Activity failure vs workflow failure

With `--fail 3`, the activity fails 3 times but the workflow succeeds: retries are invisible to workflow code. With `--fail 6`, the activity exhausts its 5 attempts and `execute_activity` raises `ActivityError` inside the workflow. Uncaught, that fails the workflow, and your starter gets `WorkflowFailureError`.
