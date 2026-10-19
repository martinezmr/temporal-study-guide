# Day 29 — Solution: NetworkComplianceOrchestrator

| File | Role |
| --- | --- |
| `workflows.py` | The orchestrator: detection loop, queue + concurrency cap, risk-based routing, continue-as-new |
| `upgrade.py` | `DeviceUpgradeWorkflow`: pre-checks → image → window (with override) → reload → wait → post-checks |
| `workers.py` | Three roles (`compliance`, `device-io`, `orchestration`), plus `setup`, `start` and `all` |
| Reused | Day 17 saga, Day 20 search attributes, Day 24 Nexus contract + handler, Day 25 explanations, Day 27 approvals |

## Run the whole system in the lab

```bash
./lab/start-temporal.sh
uv run python -m solutions.day29.workers setup     # Nexus endpoint
uv run python -m solutions.day29.workers all       # terminal 1: all three roles
uv run python -m solutions.day29.workers start     # terminal 2
temporal workflow query --workflow-id network-compliance-orchestrator --type get_state
uv run pytest solutions/tests/test_day29.py
```

In mock mode (the default), the first cycle finds the two built-in drifts:

- **bos-acc-01** is missing NTP → risk **low** → Nexus → `ConfigComplianceWorkflow` in `compliance` fixes it.
- **nyc-rtr-01** is on the wrong version → `DeviceUpgradeWorkflow` waits for 02:00 Central. Skip the wait with: `temporal workflow signal --workflow-id capstone-upgrade-nyc-rtr-01 --name override_window`.

To try the approval path, remove the AAA line from a device (in live mode, or `mock_lab.remove_line("nyc-acc-01", "aaa authorization exec default local")` in a script). It's classified **medium** and waits for `uv run python -m solutions.day27.run decide ...`. Use workflow ID `capstone-approval-nyc-acc-01` with the Day 27 commands, or the UI.

## Routing table

| Drift | Risk (Day 25) | Path |
| --- | --- | --- |
| Config, low | NTP, logging, descriptions | Nexus `remediate` → saga in `compliance` (or a direct child when `use_nexus=False`) |
| Config, medium/high | AAA, SNMP, ACLs, routing, interfaces | `ProposedRemediationWorkflow`: a human approves the real diff |
| Version | — | `DeviceUpgradeWorkflow` child, in the maintenance window |

## Design decisions

- **Remediations are asyncio tasks inside the orchestrator** that await the child or Nexus result, so the outcome lands in `completed` without children having to signal back (compare with Day 16).
- **The trade-off:** a run must drain `in_flight` before continue-as-new, because tasks don't survive the boundary. That's why `max_cycles_per_run` is a soft limit. Anything still queued is carried in `pending`.
- **Every child uses `ParentClosePolicy.ABANDON`**: terminating or resetting the orchestrator never kills a device change halfway.
- **`static_summary`** puts the LLM's one-line explanation on each child, so the UI list reads like a change log.
- **Exercise:** route the children's activities to `netops-device-io` (pass `task_queue=` as on Day 21) so only device-io pods need device access.
