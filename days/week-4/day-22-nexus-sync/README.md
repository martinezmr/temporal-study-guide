# Day 22 — First Nexus service (sync operation)

[← Week 3](../../week-3/README.md) · [Day 23 →](../day-23-nexus-async/README.md)

## Goal

A workflow in `default` calls an operation served by a worker in `compliance`, through an endpoint.

## Understand it first

*About 3 minutes.*

So far everything lives in one namespace, owned by you. Real organizations aren't shaped like that. The compliance team owns how remediation works; an inventory team owns intent; change management owns tickets. Each wants to deploy on its own schedule, without sharing code or credentials. **Nexus** is Temporal's way to call across those boundaries durably.

**The problem Nexus solves.** Without it, if your orchestrator wants the compliance team's remediation, you'd have to start their workflow directly. That means knowing their workflow type name, task queue and namespace, importing their code, and having permission in their namespace. Every refactor on their side breaks you. It's the same coupling problem that APIs solve for services.

**The pieces:**

| Piece | What it is | Network analogy |
| --- | --- | --- |
| **Service contract** | A named set of operations with typed inputs and outputs | An API spec |
| **Operation** | One callable thing: `get_policy`, `remediate` | An API endpoint |
| **Handler** | Code implementing the operations, run by a worker in the handler's namespace | The service behind the API |
| **Endpoint** | A named route registered on the server: `compliance-endpoint` → namespace `compliance`, task queue `compliance-tq` | A DNS name / VIP pointing at the service |

The caller knows only the **contract** and the **endpoint name**. The endpoint maps that name to wherever the handler actually runs. The compliance team can move task queues, rewrite their handler, or move namespaces by re-pointing the endpoint, and no caller changes.

```
default namespace                          compliance namespace
PolicyCallerWorkflow                       worker: nexus_service_handlers=[ComplianceServiceHandler()]
  create_nexus_client(ComplianceService,         ▲
                      endpoint="compliance-endpoint")
  execute_operation(get_policy, ...)  ──▶ endpoint ──┘
```

**Defining a contract** is a class of typed operation fields:

```python
@nexusrpc.service
class ComplianceService:
    get_policy: nexusrpc.Operation[PolicyRequest, Policy]
```

The handler class is decorated with `@nexusrpc.handler.service_handler(service=ComplianceService)`, and its worker registers it with `nexus_service_handlers=[...]`. A worker without that parameter doesn't poll for Nexus requests at all.

**Sync vs async operations.** Today's `get_policy` is a **sync** operation: the handler computes the answer during the request and returns it. Temporal gives sync handlers a short deadline (around 10 seconds), so they suit lookups and quick validations. Anything long or durable, like a remediation, should be an **async** operation backed by a workflow. That's tomorrow.

**It's durable from the caller's side.** In the caller's history you'll see `NexusOperationScheduled` → `NexusOperationCompleted`. If the handler's worker is down, the server retries delivering the request, and the caller just waits. The caller gets Temporal's usual guarantees across the boundary, with no retry logic of its own.

**Security and multi-tenancy.** Endpoints are registered by operators (`temporal operator nexus endpoint create`). In Temporal Cloud, an endpoint carries an allowlist of caller namespaces. Callers never get credentials for the handler's namespace; they're allowed to call that endpoint and nothing more.

**Status in Python.** Nexus is generally available for the Python SDK as of Temporal's Replay 2026 announcements. Some newer conveniences (such as the `temporal_operation` handler style) are still marked experimental, which is why this course uses the stable `sync_operation` and `workflow_run_operation` decorators.

**Why it matters for your design.** It gives the compliance logic a clean API boundary, so the orchestrator stays a decision-maker. And it's exactly how you'd later connect to other teams' services: "get intent" from an inventory team, "open a change" from an ITSM integration.

**What you'll practise today:** a contract, a handler in the `compliance` namespace, an endpoint, and a caller in `default`. You'll confirm that the two sides share nothing but the contract module.

## Build

1. **Contract** — `nexus/compliance_service.py` (shared by both sides):

    ```python
    import nexusrpc
    from pydantic import BaseModel

    class PolicyRequest(BaseModel):
        role: str

    class Policy(BaseModel):
        role: str
        required_lines: list[str]

    @nexusrpc.service
    class ComplianceService:
        get_policy: nexusrpc.Operation[PolicyRequest, Policy]
    ```

2. **Handler** — `nexus/compliance_handler.py`:

    ```python
    @nexusrpc.handler.service_handler(service=ComplianceService)
    class ComplianceServiceHandler:
        @nexusrpc.handler.sync_operation
        async def get_policy(self, ctx: nexusrpc.handler.StartOperationContext,
                             req: PolicyRequest) -> Policy:
            return POLICIES[req.role]
    ```

3. **Handler worker** — `workers/compliance.py`, connected to namespace `compliance`, task queue `compliance-tq`, with `nexus_service_handlers=[ComplianceServiceHandler()]`.
4. **Endpoint:**

    ```bash
    temporal operator nexus endpoint create \
      --name compliance-endpoint \
      --target-namespace compliance \
      --target-task-queue compliance-tq
    ```

5. **Caller** — in a workflow on `default`:

    ```python
    nexus = workflow.create_nexus_client(service=ComplianceService, endpoint="compliance-endpoint")
    policy = await nexus.execute_operation(ComplianceService.get_policy, PolicyRequest(role="access"),
                                           schedule_to_close_timeout=timedelta(seconds=30))
    ```

## Look for

`NexusOperationScheduled` → `NexusOperationCompleted` in the caller's history.

## Troubleshooting

If `endpoint create` fails, your CLI/server image predates Nexus GA. Pull a newer `admin-tools` image, or (older builds) start the dev server with `--http-port 7243 --dynamic-config-value system.enableNexus=true`.

## Done when

- [ ] The caller workflow gets a policy back, and the two namespaces share nothing but the contract module.

## Solution

Try it yourself first, then compare: [solutions/day22](../../../solutions/day22/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
