# Day 19 — Solution

**Files:**

- `workflows.py`: v1, v2 (patched) and v2-bad of one workflow type.
- `worker.py`: Worker Versioning config.
- `rollout.sh`: the CLI steps.
- `../tests/test_day19.py`: proves patching works, using replay.

```bash
uv run pytest solutions/tests/test_day19.py -v
bash solutions/day19/rollout.sh
```

## What the test proves

1. A history recorded by **v1** replays cleanly against **v2**, because `workflow.patched()` returns `False` when the history has no marker.
2. The same history fails to replay against **v2-bad** with `NondeterminismError`.

That is exactly the check your CI pipeline runs on Day 30 against real exported histories.

## Patch lifecycle

1. `if workflow.patched("x"): new` → deploy and wait until no runs without the marker remain.
2. `workflow.deprecate_patch("x")` + unconditional new code → deploy.
3. Delete the `deprecate_patch` line.

## PINNED or AUTO_UPGRADE for your workflows

| Workflow | Behaviour | Why |
| --- | --- | --- |
| `ConfigComplianceWorkflow` | PINNED | Minutes long; finishing on the code it started with is simplest and safest |
| `DeviceUpgradeWorkflow` | PINNED | Same, even if it waits hours for a window: old builds stay up until it drains |
| `NetworkComplianceOrchestrator` | AUTO_UPGRADE | Lives forever. Pinning would keep an old build alive forever. Protect changes with patches, or move it to the new build at its next continue-as-new |
| `DeviceEntityWorkflow` | AUTO_UPGRADE | Same reasoning |
