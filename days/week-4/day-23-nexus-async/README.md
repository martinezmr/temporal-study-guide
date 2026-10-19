# Day 23 — Async Nexus operations backed by workflows

[← Day 22](../day-22-nexus-sync/README.md) · [Day 24 →](../day-24-nexus-contracts/README.md)

## Goal

The orchestrator triggers remediation through Nexus, and remediation runs as a full workflow in the `compliance` namespace.

## Understand it first

*About 3 minutes.*

Yesterday's operation answered within a single request. Remediation can take minutes, involves several device calls, and must roll back on failure, so it's an **async Nexus operation backed by a workflow**. This is the main way you'll use Nexus.

**How a workflow-backed operation works:**

1. The caller calls `start_operation(ComplianceService.remediate, inp)`.
2. The server routes the request through the endpoint to a handler worker in `compliance`.
3. The handler **starts a workflow** (`ConfigComplianceWorkflow`) in its own namespace and returns immediately with an **operation token**: "accepted, here's how to track it".
4. The caller's history shows `NexusOperationStarted`. The caller keeps running, waiting on the handle.
5. When the backing workflow finishes, the server delivers its result (or failure) back to the caller as `NexusOperationCompleted` (or `Failed`).

```python
@nexus.workflow_run_operation
async def remediate(self, ctx: nexus.WorkflowRunOperationContext, input: ComplianceInput):
    return await ctx.start_workflow(ConfigComplianceWorkflow.run, input, id=f"compliance-{input.device}")
```

The handler is a few lines. All the real logic stays in the workflow you built on Day 17, now owned and deployed by the "compliance team".

**What each side sees.** The caller sees an operation: started, then completed with a `ComplianceResult`. It doesn't see the saga's internal steps. The handler side sees a normal workflow with full history. The UI links the two both ways, so you can click from the orchestrator's history to the remediation and back. It's like calling a child workflow, except the child lives in someone else's namespace and is reached through a contract.

**Durability across the boundary.** Every hop is recorded and retried. If the handler's worker is down when the request arrives, the start is retried until it succeeds. If the caller's worker is down when the result arrives, the result waits in the caller's history. Neither team writes retry logic for the other.

**Cancellation crosses the boundary too.** The caller can cancel an operation it started:

```python
handle = await nexus_client.start_operation(ComplianceService.remediate, inp)
...
handle.cancel()
```

The cancel request travels to the handler, which cancels the backing workflow. `ConfigComplianceWorkflow` catches `CancelledError`, runs its `abort_session` compensation (Day 17), and re-raises. The caller can choose how long to wait for that:

| Cancellation type | Caller waits for… |
| --- | --- |
| `WAIT_COMPLETED` (default) | The backing workflow to finish cancelling (rollback done) |
| `WAIT_REQUESTED` | The handler to acknowledge the cancel request |
| `TRY_CANCEL` | Nothing. Sends the request and moves on |
| `ABANDON` | Doesn't even send it |

For device changes, the default is right: you want the rollback finished before the orchestrator moves on. One caveat: pending cancellations aren't delivered after the caller's workflow completes, so don't finish the caller while operations are still settling.

**Idempotency via IDs, again.** The handler starts the workflow with a deterministic ID (`compliance-<device>`). If the caller retries, or two callers ask to remediate the same device at once, Temporal's one-running-workflow-per-ID rule prevents a duplicate remediation on the handler side too.

**Timeouts.** `schedule_to_close_timeout` on the operation bounds the whole thing from the caller's view: "if remediation hasn't finished in 2 hours, give up and tell me". Tomorrow covers what the caller should do when that happens.

**What you'll practise today:** moving `ConfigComplianceWorkflow` behind a Nexus operation, calling it from the `default` namespace, stopping the handler worker mid-flight, and cancelling a remediation from the caller to watch the rollback happen on the other side.

## Build

1. Add to the contract: `remediate: nexusrpc.Operation[RemediationRequest, RemediationResult]`.
2. Handler, using a workflow-run operation:

    ```python
    @nexus.workflow_run_operation
    async def remediate(self, ctx: nexus.WorkflowRunOperationContext,
                        req: RemediationRequest) -> nexus.WorkflowHandle[RemediationResult]:
        return await ctx.start_workflow(
            ConfigComplianceWorkflow.run, req, id=f"compliance-{req.device}")
    ```

3. Move `ConfigComplianceWorkflow` and its activities to the compliance worker.
4. Orchestrator: replace the direct child with

    ```python
    handle = await nexus.start_operation(ComplianceService.remediate, req)
    # ...later
    result = await handle
    ```

## Learn

- `start_operation` returns a handle you can await later or `cancel()`.
- Cancellation types: `WAIT_COMPLETED` (default), `WAIT_REQUESTED`, `TRY_CANCEL`, `ABANDON`.
- Pending cancellations aren't delivered after the caller workflow completes — wait for operations to settle first.

## Break it

- Stop the compliance worker mid-remediation. The orchestrator just waits. Restart; it completes.
- Cancel the caller and watch the cancellation reach `ConfigComplianceWorkflow` (and its saga run).

## Done when

- [ ] A drift detected in `default` produces a `ConfigComplianceWorkflow` in `compliance`, linked both ways in the UI.

## Solution

Try it yourself first, then compare: [solutions/day23](../../../solutions/day23/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
