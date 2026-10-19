# Day 28 — Solution

| File | What it shows |
| --- | --- |
| `workflows.py` | Agent with a free-form `run_show_command` tool |
| `../shared/activities.py` → `run_show_command` | **Allowlist** enforced in the activity: regex `^show ...`, everything else non-retryable |
| `../day26/agent.py` | **Max turns** and **token budget** in the loop |
| `mcp_server.py` | The same read-only tools as an MCP server for Claude Desktop or any MCP client |
| `agents_sdk_mcp_variant.py` | Wiring that MCP server into an OpenAI Agents SDK agent (untested here) |
| `../tests/test_day25_28.py` | Guardrail tests, including **replay of an agent history** |

```bash
uv run python -m solutions.day28.run demo "Is anything down on nyc-rtr-01?"
uv run pytest solutions/tests/test_day25_28.py -v
uv add mcp && uv run python -m solutions.day28.mcp_server
```

## Guardrail checklist

- [x] Command allowlist: in the **activity**, so no prompt can talk its way around it.
- [x] Max turns: `AgentInput.max_turns`.
- [x] Cost cap: `AgentInput.token_budget`, counted from each turn's usage.
- [x] Replay test of an agent history: `test_agent_history_replays`.
- [x] Audit: every model reply and tool call is an event in history; approvals are updates (Day 27).

## Deterministic vs not

| Deterministic (workflow code) | Not deterministic (activities) |
| --- | --- |
| The loop, turn limits, budget checks, which tools exist, what happens to a proposal, approval gates | Model replies, device output, Nautobot data |

The model only ever **suggests**. Everything that decides is code you wrote and can replay, test and version.
