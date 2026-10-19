# Day 03 — Data models and failures

[← Day 02](../day-02-eapi-activity/README.md) · [Day 04 →](../day-04-determinism/README.md)

## Goal

Typed inputs and outputs everywhere, and errors that retry only when retrying can help.

## Understand it first

*About 3 minutes.*

Two topics today that look unrelated but come from one idea: **everything that crosses a workflow boundary is stored forever in history**, so you want it typed, versionable, and failing only in ways you chose.

**Data conversion.** When a workflow calls an activity, the arguments don't travel as Python objects. They're serialized into **payloads** (JSON by default), stored in history, and deserialized on the other side, possibly on another machine, possibly next week. The **data converter** does that work.

The default converter handles dataclasses and basic types. Since you'll use pydantic models everywhere (they validate data and serialize cleanly), you switch to `temporalio.contrib.pydantic.pydantic_data_converter`. It must be set on **every** client that talks to these workflows: the worker's client and every starter. If one side forgets, you'll see dicts where you expected models, or deserialization errors.

**The single-input-object pattern.** Compare:

```python
async def run(self, device: str, retries: int, dry_run: bool)   # fragile
async def run(self, req: FactsRequest)                          # durable
```

Workflows can run for days, and the input of every running workflow is already in history. If you add a fourth positional parameter, old workflows replaying with three arguments break. If you add an **optional field with a default** to `FactsRequest`, old payloads still deserialize, because the new field just takes its default. The rule for every model that crosses a boundary: add optional fields freely; never rename, remove, or change the type of an existing field. It's the same discipline as evolving a public API, because that's what these models are.

**Failures: retryable vs non-retryable.** Yesterday every failure retried. That's wrong for some errors:

- **Transient** (timeout, connection refused, HTTP 503): the world may fix itself, so retry.
- **Permanent** (HTTP 401 bad password, invalid command, unknown device): retrying just wastes time and hides the real problem. With default settings, a wrong password would retry for hours while you wonder why nothing works.

You mark permanent failures by raising `ApplicationError(message, type="AuthError", non_retryable=True)` from the activity. The `type` string is important: it's how callers identify the error without parsing messages. A caller can also list types in `RetryPolicy(non_retryable_error_types=["AuthError"])`. The first puts the decision in the activity (it knows the error is permanent); the second puts it in the caller (it knows it doesn't want to wait). Using both is fine.

**How errors surface.** When an activity fails for good, the workflow's `await` raises `ActivityError`, whose `.cause` is your `ApplicationError`. If the workflow doesn't catch it, the workflow fails with that error chain, and your starter receives `WorkflowFailureError` → `ActivityError` → `ApplicationError(type="AuthError")`. Learn to read this chain; every Temporal failure is shaped like it.

**One more distinction to remember for later.** In workflow code, raising `ApplicationError` **fails the workflow**: a clean, recorded outcome. Raising any other exception (a `KeyError`, say) **fails the workflow task** instead. Temporal assumes that's a bug, and the task retries until you deploy a fix. This is deliberate: a typo shouldn't permanently fail a long-running workflow. When you mean "this workflow has failed", raise `ApplicationError`.

**Why this matters for the orchestrator:** it will juggle dozens of models (intent, state, drift reports, proposals) across months of continue-as-new runs and many deployments. Getting into typed models and deliberate error types now saves a lot of pain later.

## Learn

- **Single input object:** one pydantic model per workflow/activity input, so you can add fields later without breaking running workflows.
- The Pydantic data converter: `from temporalio.contrib.pydantic import pydantic_data_converter`, set on `Client.connect(..., data_converter=pydantic_data_converter)` for both worker and starter.
- `ApplicationError(msg, non_retryable=True)` stops retries. Or list error type names in `RetryPolicy(non_retryable_error_types=[...])`.
- Docs: [Payload conversion](https://docs.temporal.io/develop/python/data-handling/data-conversion) · [Error handling](https://docs.temporal.io/develop/python/best-practices/error-handling)

## Build

1. `models.py`:

    ```python
    class DeviceFacts(BaseModel):
        device: str
        model: str
        version: str

    class DeviceIntent(BaseModel):
        device: str
        role: str
        site: str
        target_version: str
        config_lines: list[str] = []

    class DeviceState(BaseModel):
        device: str
        version: str
        running_config: str

    class DriftReport(BaseModel):
        device: str
        config_diff: list[str] = []
        version_drift: bool = False

        @property
        def drifted(self) -> bool:
            return bool(self.config_diff) or self.version_drift
    ```

2. Switch `get_device_facts` to return `DeviceFacts`.
3. In the eAPI client, map HTTP 401/403 to `ApplicationError("auth failed", type="AuthError", non_retryable=True)`. Leave timeouts and 5xx retryable.

## Break it

- Put a wrong password in `.env`. The workflow should fail after **one** attempt with `AuthError`.
- Stop a node instead. It should still retry.
- Add a new optional field to `DeviceFacts` while a workflow is mid-retry. Nothing breaks.

## Done when

- [ ] No `dict` crosses a workflow/activity boundary anymore.
- [ ] You can say which of your errors are retryable and why.

## Solution

Try it yourself first, then compare: [solutions/day03](../../../solutions/day03/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
