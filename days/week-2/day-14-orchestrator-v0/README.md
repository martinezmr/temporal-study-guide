# Day 14 — Mini-project: Orchestrator v0

[← Day 13](../day-13-entity-workflows/README.md) · [Week 3 →](../../week-3/README.md)

## Goal

The first version of `NetworkComplianceOrchestrator`: detect and report drift, no remediation yet.

## Understand it first

*About 3 minutes.*

Today you assemble Week 2 into the first version of the system you're building toward. It helps to see the orchestrator's design as a few deliberate decisions, because you'll extend each one in Weeks 3 and 4.

**What the orchestrator is:** an entity workflow (Day 13) with a fixed ID, `network-compliance-orchestrator`, that loops forever:

```
every 15 min (or force_check):
    devices  ← Nautobot                      (activity)
    for each device, in parallel:
        intent ← Nautobot                    (activity)
        state  ← device                      (activity)
        drift  ← compare(intent, state)      (activity)
    store drift reports in state
    every 50 cycles → continue-as-new(state)
```

**Decision 1: compare in an activity, not in the workflow.** Comparing config looks like pure logic, so why not do it in workflow code? Because you'll change what "compliant" means constantly: ignore ordering, normalize whitespace, add new rule types. Every change to workflow code risks non-determinism for running workflows (Day 4) and needs versioning (Day 19). Activity code can change freely between deploys, because only its *result* is in history. A good rule: **workflows orchestrate, activities compute.** Keep the workflow a thin decision layer.

**Decision 2: nested fan-out with failure isolation.** Each device's check fetches intent and state in parallel, and all devices run in parallel. One unreachable device is recorded in `unreachable` and doesn't fail the cycle. A monitoring loop that dies because one switch rebooted is worse than useless.

**Decision 3: one state model.** `OrchestratorState` holds everything durable: interval, cycle count, paused flag, latest reports. It's the workflow's input, the `continue_as_new` argument and the query result, all at once. When you add fields in Week 3 (`in_flight`, `pending`), they carry across runs automatically, as long as you give them defaults so old payloads still load.

**Decision 4: a control plane of messages.**

| Message | Type | Purpose |
| --- | --- | --- |
| `get_drift()` | Query | What's drifted right now |
| `get_state()` | Query | Everything, for debugging |
| `pause` / `resume` | Signals | Change freeze |
| `force_check` | Signal | Check now (after a manual fix) |
| `set_interval(n)` | Signal | Tune without redeploying |

Notice that nothing here needs an update yet: no request needs a reply. That changes once you add approvals.

**Decision 5: safe to start repeatedly.** The starter uses `id_conflict_policy=USE_EXISTING`, so running it twice doesn't fail or duplicate. It just attaches to the running orchestrator. In production, a deploy pipeline can always run the starter without worrying about state.

**Timers, not cron.** The 15-minute cadence is a `wait_condition(..., timeout=15m)` inside the workflow, not an external scheduler. That lets `force_check` short-circuit it, lets `set_interval` change it live, and keeps the loop's state (what's in flight, what's pending) in one place. Day 18 covers when an external Schedule is the better choice.

**What v0 deliberately doesn't do:** fix anything. Reporting first is also how you'd roll this out for real. Run it read-only for a while, trust its drift reports, then let it act. Week 3 adds the action, carefully: children for remediation (Day 15), dedup and concurrency limits (Day 16), and rollback (Day 17).

**Done means:** it has run for at least a day, through at least one continue-as-new, while you changed and reverted device config by hand and watched the drift appear and clear.

## Build

`workflows/orchestrator.py`, workflow ID `network-compliance-orchestrator`:

1. Every `interval` (default 15 min, timer), fetch intent for all devices from Nautobot and state from all 4 devices — activities, in parallel.
2. `compute_drift(intent, state) -> list[DriftReport]` — **an activity**, so diff logic can change freely without versioning the workflow.
3. Store the latest reports in state.
4. Handlers:
    - Query `get_drift() -> list[DriftReport]`
    - Signals `pause`, `resume`, `force_check`, `set_interval(minutes)`
5. Continue-as-new every 50 cycles or when suggested, carrying `OrchestratorState`.

Starter: `starters/orchestrator.py` uses `start_workflow(..., id_conflict_policy=USE_EXISTING)` so re-running it is safe.

## Break it

- Change an interface description on `bos-acc-01` by hand. Within one cycle (or right after `force_check`), `get_drift` shows it.
- Revert it. The drift clears on the next cycle.
- Restart everything (worker, Temporal container). The orchestrator carries on.

## Done when

- [ ] The orchestrator has run for at least 24 hours across at least one continue-as-new.
- [ ] Tests cover: drift detected, drift cleared, `force_check` short-circuits the timer (time-skipping).

## Solution

Try it yourself first, then compare: [solutions/day14](../../../solutions/day14/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
