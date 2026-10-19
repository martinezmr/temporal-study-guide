# Day 07 — Solution

**Files:** `workflows.py`, `../shared/nautobot.py` (GraphQL inventory + intent), `../shared/activities.py` → `list_devices`, `get_running_config`, `save_backups`, `get_intent`.

```bash
uv run python -m solutions.day07.run demo
uv run python -m solutions.day07.run demo --break nyc-acc-01
uv run pytest solutions/tests/test_day07.py
```

## What to notice in the history

- One `ActivityTaskScheduled` for `list_devices`, then **four `ActivityTaskScheduled` events in the same workflow task**: that's the fan-out. They complete in whatever order the devices answer.
- With `--break`, one `ActivityTaskFailed` appears, the workflow still completes, and the report lists the device under `failed`.
- `save_backups` writes `backups/<device>.cfg`. It is idempotent: if the worker dies after writing and the activity retries, the result is the same.

## Why `return_exceptions=True`

Without it, `asyncio.gather` raises on the first failure and the workflow fails, losing three good backups. With it, failures come back as `ActivityError` values you can report.

## Stretch: intent from Nautobot

`shared/nautobot.py` reads intent from each device's **config context** (`target_version`, `required_lines`). Add a context like this to the four devices in Nautobot:

```json
{"target_version": "4.32.0F", "required_lines": ["ntp server 10.0.0.1", "logging host 10.0.0.50"]}
```

The mock lab uses the same shape, so Week 2 works identically in both modes.
