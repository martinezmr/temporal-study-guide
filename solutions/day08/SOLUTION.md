# Day 08 — Solution

**Files:** `workflows.py` → `DeviceWatchWorkflow`, `run.py` (start / signal from Python).

```bash
uv run python -m solutions.day08.run worker
uv run python -m solutions.day08.run start bos-rtr-01 --interval 60
uv run python -m solutions.day08.run signal bos-rtr-01 pause
uv run python -m solutions.day08.run signal bos-rtr-01 force_check   # ignored while paused...
uv run python -m solutions.day08.run signal bos-rtr-01 resume        # ...and runs right after resume
uv run pytest solutions/tests/test_day08.py
```

## Patterns worth copying

- **Signal handlers only flip state.** No activities or sleeps inside them. The main loop reacts.
- **`wait_condition(fn, timeout=...)`** is the "sleep, but wake early" primitive. It raises `asyncio.TimeoutError` when the timer wins.
- **A `stop` signal** ends the loop cleanly. Terminating also works but skips any cleanup code.
- **`id_conflict_policy=USE_EXISTING`** makes `start` safe to run twice: the second call just returns the running workflow.

## Signal while the worker is down

The signal is written to history as `WorkflowExecutionSignaled` the moment you send it. When a worker comes back, it replays history, re-applies the signal, and carries on.
