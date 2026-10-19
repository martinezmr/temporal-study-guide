# Day 18 — Solution

**Files:** `workflows.py` → `FullComplianceAuditWorkflow` (stateless), `run.py` → every schedule operation from Python.

```bash
uv run python -m solutions.day18.run worker
uv run python -m solutions.day18.run create
uv run python -m solutions.day18.run trigger
uv run python -m solutions.day18.run describe
uv run pytest solutions/tests/test_day18.py
```

The same operations from the CLI:

```bash
temporal schedule list
temporal schedule describe --schedule-id d18-nightly-compliance-audit
temporal schedule trigger  --schedule-id d18-nightly-compliance-audit
temporal schedule toggle   --schedule-id d18-nightly-compliance-audit --pause --reason "change freeze"
```

## Timer or schedule?

| | Orchestrator loop (timer) | Nightly audit (schedule) |
| --- | --- | --- |
| State between runs | Yes: in-flight remediations, pending queue | None |
| Who controls timing | The workflow itself (`force_check`, `set_interval`) | The schedule (pause, trigger, backfill in the UI) |
| One run or many | One long run + continue-as-new | A new short run each time |

## Settings used

- `time_zone_name="America/Chicago"` avoids UTC arithmetic and handles DST.
- `ScheduleOverlapPolicy.SKIP`: if last night's audit is somehow still running, don't start another.
- The scheduled workflow ID gets a timestamp suffix appended by the server, so runs never collide.
