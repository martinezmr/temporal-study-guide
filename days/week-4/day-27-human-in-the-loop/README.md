# Day 27 — AI pattern 3: human in the loop

[← Day 26](../day-26-durable-agent/README.md) · [Day 28 →](../day-28-mcp-guardrails/README.md)

## Goal

The agent may *propose* a change; only a human approval lets a deterministic workflow apply it.

## Understand it first

*About 3 minutes.*

Yesterday's agent could only look. Today it can **propose** a change, but the change only happens after a **human approves**, and the step that applies it is your deterministic Day 17 code, not the model. This is the pattern that makes AI acceptable anywhere near production networks.

**The shape of the workflow:**

```
analyse drift (activities)
  → model proposes config lines (activity)
  → deterministic guardrail checks the proposal (workflow code)
  → stage the lines in a config session; the DEVICE computes the real diff (activities)
  → wait for a human decision, up to 4 hours (update + timer)
  → approved: commit with timer → verify → confirm      rejected or timed out: abort
```

**Principle 1: the model's output is data, not action.** The model returns a `Proposal`: lines plus reasoning. The workflow decides what happens to it. No code path takes model output and executes it directly.

**Principle 2: deterministic guardrails come before anything touches a device.** Workflow code checks the proposal against a denylist: no `reload`, no `write erase`, no `no aaa`. If anything matches, the workflow fails with a non-retryable `UnsafeProposal`. It's simple, testable, and can't be argued with by a clever prompt. In production you'd extend it with an allowlist of permitted config sections per device role.

**Principle 3: approvers see the device's truth.** The proposal is staged in an Arista config session, and `show session-config diffs` gives the diff **the switch** computed. That's what the approver reviews, not the model's description of what it thinks it proposed. Models can be confidently wrong; the device's diff can't.

**Principle 4: approval is an update with a validator.** Updates (Day 10) fit approvals well:

- The approver's tool gets a reply ("recorded: approved by manny").
- The **validator** checks who's approving, rejects decisions arriving before staging is done, and blocks double decisions. Rejected attempts **aren't written to history**, so the audit trail contains only real decisions.
- Accepted decisions **are** in history: who approved what, when, with which diff. That's your change record.

**Principle 5: silence means no.** The wait is `wait_condition(decision is not None, timeout=4h)`. If nobody answers, the session is aborted and nothing changes. Never let a timeout default to "apply".

**Then the boring, reliable part.** On approval, the workflow runs the commit-with-timer → verify → confirm sequence from Day 17, with automatic rollback on failure. The AI contributed a suggestion; the safety comes from code you've already tested.

**How a human actually approves.** Anything that can call `execute_update` can approve: the CLI in the solution, a small web form, a Slack bot with Approve/Reject buttons, or an ITSM webhook. The `get_proposal` query gives it everything to display: reasoning, the real diff, the current stage. The workflow doesn't care which interface the human used.

**Durable waiting is what makes this practical.** The workflow might wait hours for an approver. It holds no thread, no connection and no lock while waiting, and it survives deploys and restarts. You couldn't do that reliably with a script that `input()`s and waits.

**What you'll practise today:** generating a proposal, inspecting the real diff with a query, approving it as an authorized user, being rejected by the validator as an unauthorized one, and letting one time out to confirm the device is untouched.

## Build

`ProposedRemediationWorkflow`:

1. Agent (Day 26) returns a structured `Proposal(device, lines, reasoning)`.
2. `stage_config` + `get_session_diff` (Day 17) — store the **real device diff**, not the model's description of it.
3. Wait for a decision, with a deadline:

    ```python
    @workflow.update
    async def decide(self, d: Decision) -> str:
        self.decision = d
        return "recorded"

    @decide.validator
    def check(self, d: Decision) -> None:
        if self.decision is not None:
            raise ValueError("already decided")
        if d.approver not in APPROVERS:
            raise ValueError("not an approver")

    try:
        await workflow.wait_condition(lambda: self.decision is not None, timeout=timedelta(hours=4))
    except asyncio.TimeoutError:
        self.decision = Decision(approved=False, approver="timeout")
    ```

4. Approved → Nexus `remediate` (commit, verify, rollback). Rejected or timed out → `abort_session`.
5. A query `get_proposal()` so an approver (or a future UI/Slack bot) can see reasoning + real diff.

## Optional

[Workflow Streams](https://docs.temporal.io/develop/python/workflows/workflow-streams) (Public Preview) to stream the agent's progress to a UI.

## Done when

- [ ] No path exists from the model to a committed config without a recorded human approval in history.

## Solution

Try it yourself first, then compare: [solutions/day27](../../../solutions/day27/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
