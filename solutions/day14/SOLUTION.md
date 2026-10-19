# Day 14 — Solution: Orchestrator v0

**Files:** `workflows.py` → `NetworkComplianceOrchestrator`, `run.py` (start / query / signal).

```bash
uv run python -m solutions.day14.run worker
uv run python -m solutions.day14.run start
uv run python -m solutions.day14.run drift
#  bos-acc-01  missing=['ntp server 10.0.0.1'] ...
#  nyc-rtr-01  missing=[] version 4.31.2F -> 4.32.0F
uv run python -m solutions.day14.run signal force_check
uv run pytest solutions/tests/test_day14.py
```

In live mode, change a description or remove a required line on a cEOS node, then `signal force_check` and `drift`.

## Design choices

- **Diff logic is an activity** (`compute_drift`). You will tweak what "compliant" means many times; activities can change freely, workflow code can't (Day 19).
- **Per-device fan-out inside a fan-out:** intent and state for each device in parallel, all devices in parallel. An unreachable device goes in `unreachable` instead of failing the cycle.
- **State is one model** (`OrchestratorState`) for Continue-As-New, and it's the query result too.
- **`stop_after_cycles`** exists only so tests and demos can end. Production leaves it `None`.

## What's next

Week 3 turns `get_drift()` into action: Day 15 starts remediation children, Day 16 adds dedup and a concurrency cap, Day 17 makes the remediation itself safe.
