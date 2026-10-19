# Day 17 — Saga: safe config push with rollback

[← Day 16](../day-16-fan-out/README.md) · [Day 18 →](../day-18-schedules/README.md)

## Goal

`ConfigComplianceWorkflow` changes a device and puts it back exactly as it was if anything fails.

## Understand it first

*About 3 minutes.*

This is the day your automation earns the right to touch production. Changing a device is easy; changing it **safely**, so that any failure leaves it exactly as it was, is the real work. The pattern is called a **saga**, and Arista gives you a device-side safety net to pair with it.

**The problem.** A remediation is several steps: stage config, check the diff, apply, verify, confirm. If verification fails after the apply, or the workflow is cancelled halfway, the device is left in an in-between state. Databases solve this with transactions, but a switch and Temporal can't share one, so you need another approach.

**The saga pattern.** For every step that changes the world, register a **compensating action** that undoes it. If anything fails later, run the compensations in reverse order:

```python
compensations = []
try:
    await stage_config(...);         compensations.append(abort_session)
    diff = await get_session_diff(...)
    await commit_with_timer(...)
    if not await verify_compliance(...):
        raise ApplicationError("verification failed", non_retryable=True)
    await confirm_commit(...)
except BaseException:
    for undo in reversed(compensations):
        await undo()
    raise
```

Because this is a Temporal workflow, the saga itself is durable. If the worker dies halfway through rolling back, a new worker replays the history, sees which compensations already ran, and finishes the rest. A script doing the same thing would leave you guessing.

**`except BaseException` catches cancellation too.** When someone clicks **Cancel** in the UI, or the parent cancels (Day 23), the workflow gets `asyncio.CancelledError` at its current `await`. You're still allowed to run activities after that, so compensation runs on cancel. Then you re-raise, so the workflow is recorded as failed or cancelled rather than silently succeeding.

**Arista config sessions: transactions on the switch.** A config session stages changes without applying them:

| Step | What the device does |
| --- | --- |
| `configure session X` + lines | Stages the lines; running config untouched |
| `show session-config named X diffs` | The exact diff the device will apply, computed by the device |
| `commit timer 00:05:00` | Applies the change, **and rolls it back automatically after 5 minutes unless confirmed** |
| `commit` (again, in the session) | Confirms; the change is permanent |
| `abort` | Discards the session (or reverts a timed commit) |

`commit timer` is the important one. It protects you even if **Temporal, the worker and your laptop all die** right after applying a change that cut the device off from management. The switch rolls itself back. With Temporal's saga on top, you have two independent layers of safety.

**The diff is your audit trail.** `get_session_diff` returns what the *device* says will change, and its result is stored in history forever. Six months from now, "what exactly did automation change on bos-acc-01 on the 14th?" has a precise answer. That's also why Day 27 shows approvers the device's diff rather than a model's description.

**Non-retryable verification failures.** If verification fails, pushing the same lines again won't help, and it could make things worse. Raise `ApplicationError(..., non_retryable=True)`, roll back, and let the workflow fail visibly so a human looks at it.

**Idempotency again.** Each step is safe to retry. Staging the same lines into the same session twice is harmless; aborting an already-aborted session is caught and ignored. The session name comes from `workflow.uuid4()`: unique per run, identical on replay.

**Check on a real device first.** Session syntax can vary slightly between EOS releases. Run the sequence by hand on one cEOS node before trusting the workflow with it.

**What you'll practise today:** a remediation that applies, verifies and confirms; one that fails verification and leaves the device exactly as it was; and one that finds nothing to change and commits nothing.

## Learn

- **Saga:** each step that changes the world registers its undo; on failure, run the undos in reverse.
- Cleanup after cancellation: catch `asyncio.CancelledError` in the workflow, run the compensating activity, then re-raise.
- Arista config sessions give you a staged change, a real diff, and `commit timer` (auto-rollback unless confirmed) — a saga built into the device.

## Build

Activities (eAPI):

| Activity | eAPI commands |
| --- | --- |
| `stage_config(device, session, lines)` | `configure session <s>`, the lines, `end` |
| `get_session_diff(device, session)` | `show session-config named <s> diffs` |
| `commit_with_timer(device, session, minutes)` | `configure session <s>`, `commit timer 00:05:00` |
| `verify_state(device, intent)` | re-pull running config, re-diff against intent |
| `confirm_commit(device, session)` | `configure session <s>`, `commit` |
| `abort_session(device, session)` | `configure session <s>`, `abort` |

Workflow:

```python
compensations: list[Callable[[], Awaitable]] = []
try:
    await act(stage_config, ...);      compensations.append(lambda: act(abort_session, ...))
    diff = await act(get_session_diff, ...)   # stored in history = audit trail
    await act(commit_with_timer, ...)  # device rolls back by itself if we never confirm
    ok = await act(verify_state, ...)
    if not ok:
        raise ApplicationError("verification failed", non_retryable=True)
    await act(confirm_commit, ...)
except BaseException:
    for undo in reversed(compensations):
        await undo()
    raise
```

Check the exact session commands against your cEOS version — run them by hand first.

## Break it

- Make `verify_state` return `False`. The device must end up with its original config.
- Kill the worker after `commit_with_timer`. The device's own timer rolls back even if Temporal never returns — two layers of safety.

## Done when

- [ ] A diff from Nautobot intent lands on the device, is verified, and confirmed.
- [ ] A failed verification leaves no trace on the device.

## Solution

Try it yourself first, then compare: [solutions/day17](../../../solutions/day17/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
