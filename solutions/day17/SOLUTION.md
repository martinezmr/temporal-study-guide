# Day 17 — Solution

**Files:** `workflows.py` → `ConfigComplianceWorkflow` (the real one, reused through Day 29), `../shared/activities.py` → the six config-session activities, `../shared/mock_lab.py` → session behaviour in the fake switch.

```bash
uv run python -m solutions.day17.run demo bos-acc-01
uv run python -m solutions.day17.run demo bos-acc-01 --fail-verify
uv run pytest solutions/tests/test_day17.py
```

## Two layers of safety

1. **Temporal saga:** each step that changes the device registers its undo (`abort_session`). On any failure, or on cancellation, the undos run in reverse. The failure is then re-raised, so the workflow still shows as failed.
2. **The device's own timer:** `commit timer 00:05:00` rolls the change back on the switch itself unless `commit` confirms it. If the worker, Temporal and your laptop all died right after the commit, the switch still recovers.

## Details that matter

- **The diff is stored in history** (`get_session_diff`'s result). That's your audit trail: exactly which lines were going to change, taken from the device rather than from intent.
- **"Already compliant" short-circuits** and aborts the empty session, so it never commits nothing.
- **`except BaseException`** catches `asyncio.CancelledError` too. After a workflow is cancelled you can still run activities in the handler, so compensation runs when someone hits **Cancel** in the UI.
- **Verification failure is `non_retryable`**. Re-pushing the same lines won't make verification pass. Roll back and let a human look.
- **Session names use `workflow.uuid4()`**: unique per run, identical on replay.

## Live-mode check

Run the session commands by hand on one cEOS node first. Syntax for `commit timer` and session `abort` can vary slightly by EOS release:

```
configure session test1
ntp server 10.0.0.1
end
show session-config named test1 diffs
configure session test1
commit timer 00:05:00
configure session test1
abort
```
