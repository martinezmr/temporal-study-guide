# Day 26 — Solution

The main solution hand-writes the agent loop, so you can see exactly what a durable agent is. `agents_sdk_variant.py` shows the same agent with Temporal's OpenAI Agents SDK plugin.

| File | Role |
| --- | --- |
| `llm_step.py` | One model turn = one activity (real Claude with a key, scripted mock without) |
| `tools.py` | Tool registry: each tool is an existing read-only activity, plus its JSON schema |
| `agent.py` | `run_agent()`: model → tools in parallel → model …, with max turns and a token budget |
| `workflows.py` | `TroubleshootingAgentWorkflow` with read-only tools |
| `agents_sdk_variant.py` | Same agent via `temporalio-openai-agents` (untested here; check import paths) |

```bash
uv run python -m solutions.day26.run demo "Why can't bos-acc-01 reach bos-rtr-01?"
uv run pytest solutions/tests/test_day25_28.py -k agent
```

## Read the history

Each turn is an `ActivityTaskCompleted` for `llm_step`, followed by one activity per tool call, all scheduled in the same workflow task, since tools run in parallel. Kill the worker mid-investigation and restart it: completed turns aren't repeated, and the agent continues from the next one.

## Design notes

- **Messages live in workflow state.** They're rebuilt identically on replay because every model reply comes from history.
- **Tool failures go back to the model** as `is_error` results rather than failing the workflow, the same way a human would see an error and try something else.
- **Read-only by construction:** this workflow only registers read-only tools. Changes are Day 27's job, behind an approval.
- **Large histories:** long conversations make big payloads. For production agents, look at continue-as-new between investigations, or External Payload Storage.
