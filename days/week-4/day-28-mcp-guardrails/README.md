# Day 28 — AI pattern 4: MCP tools and guardrails

[← Day 27](../day-27-human-in-the-loop/README.md) · [Capstone →](../../capstone/day-29-assemble-orchestrator/README.md)

## Goal

Reusable network tools over MCP, and guardrails you can prove with tests.

## Understand it first

*About 3 minutes.*

Today rounds out AI week with two things: **guardrails you can prove with tests**, and **MCP**, a standard way to expose your tools to any AI client.

**Guardrails belong in code, not in prompts.** A system prompt saying "only run show commands" is a request, and models don't always honour requests. A guardrail is something the model *can't* get around:

| Guardrail | Where it lives | What it stops |
| --- | --- | --- |
| **Command allowlist** | Inside the `run_show_command` **activity**: regex `^show ...`, anything else non-retryable | A model (or prompt injection) issuing `configure terminal` |
| **Max turns** | The agent loop in the workflow | Runaway loops that never conclude |
| **Token budget** | The agent loop counts usage from each model reply | Surprise bills; investigations that sprawl |
| **Tool scoping** | Which tools a workflow registers | Read-only agents calling write tools |
| **Approval gate** | Day 27's update + timeout | Any change without a human |

Put the allowlist in the **activity** rather than the workflow or the prompt, because the activity is the last code that runs before the device. Whatever path leads there (this agent, a future agent, an MCP client), the check runs.

**Test the guardrails like any other feature.** Tests can swap in a fake "model" activity registered under the same name (Day 6's mocking trick) that misbehaves on purpose: one that keeps asking for `configure terminal`, one that reports enormous token usage. The tests then assert the workflow stopped for the right reason and that no forbidden command ever reached the device. Your safety story isn't "we told the model not to"; it's "here are the tests proving it can't".

**Replay tests for agents.** Agent workflows are workflows, and they must replay deterministically after code changes too. A replay test of a recorded investigation catches changes to the loop that would break in-flight agents, the same Day 6 discipline applied to AI.

**MCP: one tool server, many AI clients.** The **Model Context Protocol** is an open standard for exposing tools (and other context) to AI applications. Write an MCP server once, and Claude Desktop, IDE assistants and agent frameworks can all use its tools. Today you wrap your read-only lookups (`show`, interfaces, LLDP) in a small MCP server using the Python `mcp` package's FastMCP helper.

Two ways MCP and Temporal meet:

1. **Temporal agents using MCP tools.** The OpenAI Agents SDK integration can register MCP servers on the worker and reference them from durable agents (`temporal_mcp_server("netops")`), so MCP tool calls get Temporal's retries and history like any other activity.
2. **MCP tools backed by Temporal.** The reverse is also common: an MCP tool that *starts a workflow*, such as "propose a fix for bos-acc-01", so a chat assistant can kick off durable, approved work.

Today's MCP server calls devices directly, because its tools are quick, read-only lookups where a workflow would add little. Anything that changes the network still goes through `ProposedRemediationWorkflow`.

**The deterministic / non-deterministic split, one last time:**

- **Deterministic (workflow code, yours):** the loop, limits, budgets, tool lists, guardrails, what happens to a proposal, approval gates, commit and rollback.
- **Non-deterministic (activities):** model replies, device output, Nautobot data.

The model only ever suggests. Everything that decides is code you wrote, can test, can replay and can version. That's why it's reasonable to point an agent at a network.

**What you'll practise today:** an agent with a free-form `show` tool, tests proving the allowlist, turn limit and budget hold against a deliberately bad model, a replay test of an agent run, and an MCP server you can connect to Claude Desktop.

## Build

1. Wrap your read-only lookups (`show` commands, Nautobot device queries) as an MCP server (e.g. with the `mcp` Python package's FastMCP).
2. Register it with the plugin and use it from the agent:

    ```python
    OpenAIAgentsPlugin(mcp_servers=[...named server factory...])
    # in the workflow
    agent = Agent(..., mcp_servers=[temporal_mcp_server("netops-tools")])
    ```

    (`uv add "temporalio-openai-agents[mcp]"`; see the integration page for the factory signature.)
3. The same MCP server now works from Claude Desktop or any MCP client too.

## Guardrails to implement

- [ ] **Command allowlist** in the tool activity: only `show ...` commands; anything else raises non-retryable.
- [ ] **Max turns** on the agent run.
- [ ] **Cost cap**: count tokens per workflow in state; stop when over budget.
- [ ] **Replay test** of a saved agent history (Day 6) — agent workflows must replay too.
- [ ] **Audit**: the approval, the real diff and the model's reasoning all live in history.

## Checkpoint

Explain which parts of the AI flow are deterministic (the workflow) and which aren't (model calls, in activities), and why that split is what makes it safe to point an agent at a network.

## Solution

Try it yourself first, then compare: [solutions/day28](../../../solutions/day28/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
