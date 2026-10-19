# Day 25 — AI pattern 1: LLM call as an activity

[← Day 24](../day-24-nexus-contracts/README.md) · [Day 26 →](../day-26-durable-agent/README.md)

## Goal

Every drift report comes with a plain-English explanation and a risk level, produced durably.

## Understand it first

*About 3 minutes.*

AI week starts with the simplest, most useful pattern: **an LLM call is an activity.** Get this right and the more ambitious patterns that follow are variations on it.

**Why an activity?** From Temporal's point of view, a call to a language model is just an external API call, and a particularly unreliable one:

- **Slow:** seconds to tens of seconds.
- **Flaky:** rate limits (HTTP 429), overloaded servers (5xx), timeouts.
- **Non-deterministic:** the same prompt can produce different answers.
- **Expensive:** you pay per token.

The first two say "needs timeouts and retries", which activities give you. The third says "must never run inside workflow code", because replay would produce a different answer than history recorded (Day 4). The fourth says "never run it twice by accident". All four point to the same answer.

**Durability gives you exactly-once results.** Once `explain_drift` completes, its result, the model's answer, is stored in history. If the worker crashes a second later, or the workflow is replayed next week, the recorded answer is reused. That has two consequences:

1. You never pay twice for the same completed call.
2. Later decisions based on that answer can't change on replay. If the model said "risk: low" and the orchestrator chose the automatic path, a replay always sees "low". Your system's behaviour is reproducible even though the model isn't.

(An attempt that fails mid-way *is* retried and may get a different answer. That's fine, because nothing was decided from the failed attempt.)

**Classify LLM errors like device errors** (Day 3):

| Response | Meaning | Treatment |
| --- | --- | --- |
| 429, 5xx | Rate-limited or overloaded | Retryable, with backoff (start around 5 s) |
| 400, 401, 403, 413 | Bad request, bad key, prompt too long | Non-retryable `ApplicationError` |
| Reply isn't the JSON you asked for | The model wandered | Retryable: a new sample usually complies |

**Ask for structure, validate it.** The orchestrator will *route on* the answer: low risk goes to automatic remediation, medium or high to a human (Day 29). A paragraph of prose is useless for that. Ask the model for JSON matching a schema, then validate it into a pydantic model (`DriftExplanation` with `risk: Literal["low", "medium", "high"]`). If validation fails, the activity fails and retries. Your workflow only ever sees well-formed data.

**Keep the model's role narrow.** Here the model **explains and classifies**; it doesn't decide or act. The workflow decides what to do with the classification. That separation, model as advisor and code as decision-maker, runs through the rest of the week.

**Choosing a model.** Classification and short explanations don't need the biggest model. A smaller, faster one is usually enough and cheaper at fleet scale. The solution reads the model from `LLM_MODEL`, so you can compare. Without an API key it falls back to a deterministic rule-based "model", which keeps tests and demos offline and shows that the workflow doesn't care where the answer came from.

**Prompt and data hygiene.** Send only what the model needs: the device name, missing lines, versions. Don't send credentials or whole configs with secrets in them. Activity inputs and outputs are stored in history, so they're also your audit record of exactly what was sent and received.

**What you'll practise today:** an `explain_drift` activity with structured output, an LLM-specific retry policy, killing the worker after the call completes to prove the answer is reused, and an invalid key to see the non-retryable path.

## Learn

- An LLM call is a slow, flaky, expensive API call: it belongs in an activity with a timeout and a retry policy.
- 429 / 5xx → retryable. 400 (bad request, prompt too long) → non-retryable.
- Durability pays twice: if the worker dies after the model answered, the answer is already in history — you don't pay for, or get a *different* answer from, the same call again.

## Build

```python
class DriftExplanation(BaseModel):
    summary: str
    risk: Literal["low", "medium", "high"]
    likely_cause: str

@activity.defn
async def explain_drift(report: DriftReport) -> DriftExplanation:
    # Use the Anthropic or OpenAI SDK with structured output / tool-forced JSON,
    # then DriftExplanation.model_validate(...)
    ...
```

- `uv add anthropic` (or `openai`); key from `.env`.
- Call it with `start_to_close_timeout=60s`, `RetryPolicy(maximum_attempts=4, non_retryable_error_types=["BadRequest"])`.
- Put the summary on the child's `static_summary` / memo so it shows in the UI.

## Break it

- Kill the worker right after the activity completes. On restart, the explanation is reused, not regenerated.
- Point the key at an invalid value — non-retryable, fails fast.

## Done when

- [ ] Every `ConfigComplianceWorkflow` shows a human-readable "why" in the UI.

## Solution

Try it yourself first, then compare: [solutions/day25](../../../solutions/day25/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
