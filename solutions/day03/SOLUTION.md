# Day 03 — Solution

**Files:** `workflows.py`, `../shared/models.py` (all models), `../shared/eapi.py` (`_check()` classifies errors), `../shared/runner.py` (pydantic converter on every client).

```bash
uv run python -m solutions.day03.run demo bos-rtr-01 --auth-fail
uv run python -m solutions.day03.run demo bos-rtr-01 --timeouts 2
uv run pytest solutions/tests/test_day03.py
```

## Error classification

| Failure | Raised as | Retried? | Why |
| --- | --- | --- | --- |
| HTTP 401/403 | `ApplicationError(type="AuthError", non_retryable=True)` | No | A wrong password won't fix itself |
| eAPI command error | `ApplicationError(type="EapiCommandError", non_retryable=True)` | No | Same command, same error |
| Unknown device | `ApplicationError(type="UnknownDevice", non_retryable=True)` | No | Config problem |
| Timeout, connection refused, 5xx | Plain exception | Yes | Device rebooting, link flap, eAPI busy |

Two ways to stop retries: raise `ApplicationError(..., non_retryable=True)` from the activity (the activity decides), or list the error `type` in `RetryPolicy.non_retryable_error_types` (the caller decides). This solution does both.

## Pydantic converter

`Client.connect(..., data_converter=pydantic_data_converter)` must be set on **both** the worker's client and the starter's client. Forget it on one side and you get dicts instead of models, or serialization errors.

## Adding a field safely

Add `max_attempts: int = 5` (with a default) to `FactsRequest` while a workflow is mid-retry: old payloads still deserialize. Removing or renaming a field is what breaks.
