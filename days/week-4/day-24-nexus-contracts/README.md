# Day 24 — Nexus errors, timeouts and contracts

[← Day 23](../day-23-nexus-async/README.md) · [Day 25 →](../day-25-llm-activity/README.md)

## Goal

Treat the Nexus contract like a public API: versioned, typed, with defined failure behaviour.

## Understand it first

*About 3 minutes.*

Once another team depends on your Nexus service, or you depend on theirs, the contract becomes a **public API**. Today is about treating it like one: a versioned package, defined failure behaviour, and timeouts every caller handles.

**The contract as a package.** The contract module, with the service definition and its pydantic models, is the only code both sides share. Put it in its own small package (here `solutions/netops_contracts/`; in real life its own repo and wheel, like `netops-contracts==1.2.0`) with a version number. Both teams depend on a version and upgrade when they choose. Give the service an explicit name, `@nexusrpc.service(name="NetOpsCompliance")`, so renaming the Python class doesn't change the wire contract.

**Evolving it safely** follows the same rules as Day 3's models, because it's the same problem: messages already in flight, and callers on older versions.

| Change | Safe? |
| --- | --- |
| Add an optional field (with a default) | ✔ |
| Add a new operation | ✔ |
| Rename or remove a field or operation | ✘ breaks callers |
| Change a field's type or meaning | ✘ |
| Need a breaking change | Add `remediate_v2`, migrate callers, then retire v1 |

**Failure is part of the API.** Callers need to know how each failure will show up and whether to retry. There are three places an operation can fail:

1. **The handler rejects the request** before starting anything (bad input, not authorized, device not under automated compliance). Raise `nexusrpc.HandlerError(..., type=HandlerErrorType.BAD_REQUEST)`. Bad-request-style errors are **non-retryable**: the caller gets a failure right away instead of the request being retried.
2. **The backing workflow fails** (verification failed and rolled back). Its `ApplicationError` travels back to the caller.
3. **The operation times out**: `schedule_to_close_timeout` passes before it finishes.

In every case, the caller's `await` raises **`NexusOperationError`**, with the underlying reason in `.cause`. The caller decides what each means:

```python
try:
    result = await nexus_client.execute_operation(ComplianceService.remediate, inp,
                                                  schedule_to_close_timeout=timedelta(hours=2))
except NexusOperationError as e:
    ...  # mark the device "manual", alert, don't retry blindly
```

For the orchestrator, a failed remediation shouldn't fail the orchestrator. It becomes an **outcome** ("manual", "failed") recorded in state and surfaced to humans. That's why the solution's caller returns a `RemediationOutcome` rather than letting the exception escape.

**Prefer typed errors to string matching.** The lab solution matches on an error message for brevity. In production, give each failure a distinct `type` (`"NotUnderCompliance"`, `"VerificationFailed"`) and inspect `e.cause.type`. Error types are part of the contract too; document them alongside the operations.

**Timeouts are a contract between teams.** The caller's `schedule_to_close_timeout` says how long it's willing to wait; the handler's workflow has its own timeouts. Make sure they agree: a caller giving up after 10 minutes on an operation that legitimately waits for a 2-hour window will report failures that aren't real.

**Why this is worth the ceremony.** With Nexus, a team can deploy a new remediation strategy on Tuesday without coordinating with anyone, provided the contract holds. That independence is what lets platform pieces scale beyond one person, and it's the same thinking you'd apply to a REST API between your orchestrator and an ITSM system.

**What you'll practise today:** moving the contract into a versioned package, an allowlist rejection in the handler, a timeout, and a caller that turns every failure mode into a clear outcome, tested end to end.

## Learn

- `schedule_to_close_timeout` on each operation call bounds the whole operation.
- Handler failures surface in the caller as `NexusOperationError` wrapping the cause. Raise non-retryable errors (e.g. `nexusrpc.HandlerError` with a non-retryable type, or `ApplicationError(non_retryable=True)` from the workflow) for "this will never work" cases.
- Contracts evolve like APIs: add optional fields, never rename or remove; add a new operation for breaking changes.

## Build

1. Move `nexus/compliance_service.py` and its models into a tiny package `netops_contracts/` with its own version. Both workers import it.
2. Make `remediate` reject devices outside an allowlist with a non-retryable error. Handle it in the orchestrator by marking the device `ComplianceState="manual"`.
3. Add a 2-hour `schedule_to_close_timeout` to `remediate`; on timeout, alert (log + search attribute).

## Design note

In production this is how an inventory, security or change-management team can expose "get device intent" or "open a change ticket" to your orchestrator without sharing a namespace, a repo, or a deploy schedule.

## Done when

- [ ] Tests cover: success, non-retryable rejection, timeout.

## Solution

Try it yourself first, then compare: [solutions/day24](../../../solutions/day24/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
