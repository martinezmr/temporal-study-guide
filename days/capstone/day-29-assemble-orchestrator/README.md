# Day 29 — Assemble NetworkComplianceOrchestrator

[← Week 4](../../week-4/README.md) · [Day 30 →](../day-30-ocp-cicd/README.md)

## Goal

Everything from the month, working together, end to end.

## Understand it first

*About 3 minutes.*

Today nothing is new; everything connects. It's worth reading the final orchestrator as a set of **responsibilities**, each one a pattern you learned on a specific day.

**What each piece is responsible for:**

| Concern | Mechanism | Day |
| --- | --- | --- |
| One brain, always running | Entity workflow with a fixed ID; continue-as-new | 13, 12 |
| Noticing drift | Timer loop + `force_check`; parallel intent/state/diff activities | 11, 7, 14 |
| Explaining drift | LLM activity with structured output | 25 |
| Not fixing the same thing twice, not fixing too much at once | `pending` queue, `in_flight` map, concurrency cap | 16 |
| Fixing low-risk config | Nexus operation → saga in the compliance namespace | 23, 17 |
| Fixing risky config | Child workflow with a human approval gate | 27 |
| Upgrading | Child workflow: pre-checks, window, reload, post-checks | 15, 11 |
| Never killing a change halfway | `ParentClosePolicy.ABANDON` | 15 |
| Being operable | Queries, signals, search attributes, summaries | 9, 8, 20 |

**Risk-based routing is the heart of it.** After drift is detected, the orchestrator asks the model to classify it, then routes deterministically on the answer:

```
config drift ── explain_drift ──┬─ risk low      → Nexus remediate (automatic, with rollback)
                                └─ medium/high   → ProposedRemediationWorkflow (human approves real diff)
version drift ─────────────────── DeviceUpgradeWorkflow (waits for the maintenance window)
```

The model contributes a judgment; your code decides what that judgment *allows*. If you ever want to tighten things, say everything goes through approval during a change freeze, it's one line of workflow code, protected by a patch.

**Tracking remediations with workflow tasks.** On Day 16, children signalled the parent when done. Here the orchestrator starts a small `asyncio` task per remediation that awaits the child or Nexus result and records the outcome. asyncio tasks are deterministic inside workflows, so this is safe. It reads more simply, and the outcome comes back typed. The trade-off: tasks don't survive continue-as-new, so the orchestrator drains in-flight remediations before rolling over. Queued devices carry across in `pending`. Seeing two valid designs with different trade-offs is part of the lesson.

**The upgrade workflow shows the full shape of a careful change**, even though the reload is simulated (cEOS can't be upgraded in place):

1. **Pre-checks:** snapshot LLDP neighbors (in production also BGP peers, routes, interface counts).
2. **Image check:** is the target image staged?
3. **Window:** a durable timer to 02:00 local, with an `override_window` signal for emergencies.
4. **Reload, then wait** for the device to come back on the target version, polling with timers and a bounded number of attempts.
5. **Post-checks:** compare with the snapshot. Any difference fails the workflow loudly for a human.

Every one of those steps survives worker restarts. A real upgrade in the middle of the night, with your laptop closed, finishes or fails visibly in the morning. It never silently stops halfway.

**Three worker roles, one codebase.** `compliance` (in the compliance namespace: Nexus handler + saga), `device-io` (activities, rate-limited), and `orchestration` (workflows). In the lab, `all` runs them in one process; on Day 30 each becomes a Deployment. The orchestration worker also hosts activities for the child workflows. Routing those to device-io, as on Day 21, is left as an exercise.

**How to read this system when something goes wrong:** start at the orchestrator's `get_state` query (what's pending, in flight, completed), click through to the child or Nexus operation for the device in question, and read its history. Every decision and every device command is there, in order.

**What you'll practise today:** running the full system, watching the two built-in drifts take different paths, overriding an upgrade window, and pushing a medium-risk drift through the approval path.

## Architecture

```
              Operators · nightly schedule · AI approvals
                         │ signals / queries / updates
┌──────────── namespace: default ─────────────┐     ┌──── namespace: compliance ────┐
│  NetworkComplianceOrchestrator (entity)     │────▶│  compliance-endpoint (Nexus)  │
│    ├─ DeviceUpgradeWorkflow (child)         │     │    └─ ConfigComplianceWorkflow │
│    └─ Troubleshooting agent (child)         │     │        (saga + rollback)       │
└──────┬───────────────┬──────────────┬───────┘     └──────────────┬────────────────┘
       │ intent        │ model calls  │ state                      │ config changes
   Nautobot         LLM API         4 × Arista cEOS ◀──────────────┘
```

The orchestrator only decides. Every device change happens in a child workflow or behind the Nexus endpoint, and every external call is an activity.

## One drift cycle

1. The 15-minute timer fires (or `force_check`, or the nightly schedule's audit).
2. Activities on `netops-device-io` fetch intent from Nautobot and state from all 4 devices in parallel.
3. `compute_drift` returns `DriftReport`s; the orchestrator upserts `ComplianceState` per device.
4. For each drifted device, `explain_drift` attaches a summary and risk level.
5. **Config drift** → Nexus `remediate` → `ConfigComplianceWorkflow` in `compliance` (through the Day 27 approval gate when risk is medium/high).
6. **Version drift** → `DeviceUpgradeWorkflow` child (`ABANDON`), waiting for the device's maintenance window.
7. Children report back; the orchestrator updates state and continues-as-new on schedule.

## DeviceUpgradeWorkflow in the lab

cEOS can't be upgraded in place, so its activities are stand-ins with the real shape:
pre-checks (BGP/LLDP snapshot) → image present? → wait for window → "reload" (a timer) → wait for reachability → post-checks diffed against pre-checks → rollback path if they differ.

## Final test

- [ ] Change an interface description on `bos-acc-01` by hand → config path runs, low risk, auto-remediated.
- [ ] Add a non-compliant ACL on `nyc-acc-01` → high risk, waits for your approval, you approve, it's fixed.
- [ ] Bump `nyc-rtr-01`'s target version in Nautobot → upgrade path waits for the window (use `emergency_override` to skip).
- [ ] Restart every container mid-run. Everything finishes.

## Solution

Try it yourself first, then compare: [solutions/day29](../../../solutions/day29/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
