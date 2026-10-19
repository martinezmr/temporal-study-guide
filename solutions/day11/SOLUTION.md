# Day 11 — Solution

**Files:** `workflows.py` → `wait_for_maintenance_window()`: a durable timer to the next 02:00 local, raced against an `override` signal.

```bash
uv run python -m solutions.day11.run worker
uv run python -m solutions.day11.run start bos-rtr-01
podman restart temporal-dev     # the timer survives this
uv run python -m solutions.day11.run override bos-rtr-01
uv run pytest solutions/tests/test_day11.py     # waits of up to ~24 h finish in milliseconds
```

## Notes

- `workflow.now()` is UTC. The solution adds a fixed offset, which is fine for a lab. In production, pass each site's IANA timezone from Nautobot. Compute the window in an **activity** with `zoneinfo` (DST rules are data that changes), or compute it in the workflow with `zoneinfo` imported through `imports_passed_through`.
- `wait_condition(..., timeout=...)` raises `TimeoutError` (`asyncio.TimeoutError` is the same class on Python 3.11+).
- Timers live on the server. The UI shows the exact fire time under **Pending**, even with every worker stopped.
- The time-skipping test server jumps straight to the next timer whenever your test is waiting on a result. That's why a 24-hour wait takes milliseconds.
