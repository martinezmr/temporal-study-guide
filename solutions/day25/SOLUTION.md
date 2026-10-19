# Day 25 — Solution

**Files:**

- `../shared/llm.py`: Messages API over HTTPS with retryable vs non-retryable errors, plus JSON extraction.
- `activities.py`: `explain_drift`, using the real model when `ANTHROPIC_API_KEY` is set and a deterministic mock otherwise.
- `workflows.py`: drift, then the explanation, with an LLM-specific retry policy.

```bash
uv run python -m solutions.day25.run demo bos-acc-01 nyc-rtr-01
ANTHROPIC_API_KEY=... uv run python -m solutions.day25.run demo bos-acc-01
uv run pytest solutions/tests/test_day25_28.py -k explain
```

## Error handling for LLM calls

| Response | Raised as | Retried? |
| --- | --- | --- |
| 429 rate limit, 5xx overloaded | `RuntimeError` | Yes, 5 s → 10 s → 20 s, 4 attempts |
| 400/401/403/404/413 | `ApplicationError(type="LLMBadRequest", non_retryable=True)` | No |
| Reply isn't valid JSON | `ApplicationError(type="BadModelOutput")` | Yes. A new sample often complies |

## Why this is the right shape

- **The model call is an activity:** it's I/O, it's slow, it fails. Activities get timeouts and retries for free.
- **Exactly-once from the workflow's point of view:** once `explain_drift` completes, its result is in history. Replays, worker crashes and redeploys reuse it. You never pay twice, and the decision a later step makes can't change because a second sample said something different.
- **Structured output:** the model must fill a pydantic model (`DriftExplanation`). The orchestrator routes on `risk` (Day 29), so a free-text answer would be useless.

## Picking a model

Set `LLM_MODEL` (default `claude-sonnet-5-5`). For a quick, cheap classification like this, a smaller model is usually enough.
