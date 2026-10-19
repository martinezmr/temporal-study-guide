# Day 24 — Solution

**Files:**

- `../netops_contracts/`: the contract as a versioned package.
- `handler.py`: allowlist rejection with `HandlerError(BAD_REQUEST)`.
- `workflows.py`: the caller turns every failure mode into an outcome.

```bash
uv run python -m solutions.day24.run setup
uv run python -m solutions.day24.run demo bos-acc-01
uv run python -m solutions.day24.run demo lab-sw-99
uv run python -m solutions.day24.run demo bos-acc-01 --fail
uv run pytest solutions/tests/test_day22_24.py
```

## Failure modes, as the caller sees them

| What happened | Where | Caller sees | Outcome |
| --- | --- | --- | --- |
| Device not allowed | Handler raises `HandlerError(BAD_REQUEST)` before starting anything | `NexusOperationError`, no retries | `manual` |
| Verification failed, rolled back | Backing workflow fails with `ApplicationError(non_retryable)` | `NexusOperationError` wrapping it | `failed` |
| Took longer than `schedule_to_close_timeout` | Server times out the operation | `NexusOperationError` (timeout cause) | `failed` |
| Handler worker down | — | Waits (Nexus retries the start) | eventually one of the above |

Matching on the error message is fine for a lab. In production, put a typed error `type` in the backing workflow's `ApplicationError` and inspect `e.cause` instead.

## Contract rules

- Version the package (`__version__`), and give the service an explicit name (`@nexusrpc.service(name="NetOpsCompliance")`) so renaming the Python class doesn't break callers.
- **Safe:** add an optional field, add an operation. **Breaking:** rename or remove a field or operation, or change a type. For a breaking change, add `remediate_v2` and migrate callers.
