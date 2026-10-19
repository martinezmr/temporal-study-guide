# Day 05 — Solution

**Files:** `workflows.py`, `../shared/activities.py` → `get_lldp_neighbors` (sync) and `collect_show_tech` (sync, heartbeating), `../shared/eapi.py` → `run_commands_sync`.

```bash
uv run python -m solutions.day05.run demo bos-rtr-01
uv run pytest solutions/tests/test_day05.py
```

## Async or sync?

| Activity | Kind | Why |
| --- | --- | --- |
| `get_device_facts`, `get_running_config` | `async def` | niquests' `AsyncSession` never blocks the loop |
| `get_lldp_neighbors`, `collect_show_tech` | `def` | Stand-ins for blocking libraries (pyeapi, netmiko, napalm). They run in `activity_executor=ThreadPoolExecutor(...)` |

The rule: blocking code in an `async def` activity freezes every other activity, and the worker's heartbeats, on that worker.

## How resume works

`collect_show_tech` calls `activity.heartbeat(i + 1)` after each command. When the worker dies, heartbeats stop. After `heartbeat_timeout` (15 s) the server fails that attempt and schedules a retry. The new attempt reads `activity.info().heartbeat_details[0]` and skips the finished commands. (In real life you'd also persist partial output somewhere, since it is lost with the old worker.)

## Cancellation

A sync activity learns about cancellation when it heartbeats; `activity.is_cancelled()` then returns `True`. An async activity gets `asyncio.CancelledError` at its next `await`. Both need a `heartbeat_timeout` for cancellation to be delivered promptly.
