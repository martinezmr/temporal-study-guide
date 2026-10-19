# Day 27 — Solution

**Files:** `activities.py` → `propose_remediation` (LLM, or mock). `workflows.py` → `ProposedRemediationWorkflow`:

1. Analyse.
2. Model proposes.
3. Deterministic guardrail.
4. Stage the change and capture the **real device diff**.
5. Wait for an approval update, with a 4-hour deadline.
6. Commit, verify and confirm, or abort.

```bash
uv run python -m solutions.day27.run worker
uv run python -m solutions.day27.run start bos-acc-01
uv run python -m solutions.day27.run show bos-acc-01
uv run python -m solutions.day27.run decide bos-acc-01 approve manny
uv run pytest solutions/tests/test_day25_28.py -k proposal
```

## Why there's no path from the model to the device

- The model's output is **data** (`Proposal.lines`). The workflow decides what happens to it.
- A **deterministic filter** (`FORBIDDEN`) rejects dangerous proposals before staging.
- The approver sees the **diff the switch computed** from the staged session, not the model's description of it.
- Only the `decide` update can move the workflow past `awaiting-approval`. Its validator checks the approver and rejects late or duplicate decisions, and rejected calls leave no trace in history.
- **No answer means no change:** the timeout path aborts the session.
- Approval, approver, diff and reasoning all end up in history: a complete audit record.

## Hooking up a real approver

Anything that can call `execute_update` can approve: a Slack bot, a small web form, a ServiceNow webhook. The query `get_proposal` gives it everything to display.
