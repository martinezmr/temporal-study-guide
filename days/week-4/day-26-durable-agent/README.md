# Day 26 — AI pattern 2: a durable agent with device tools

[← Day 25](../day-25-llm-activity/README.md) · [Day 27 →](../day-27-human-in-the-loop/README.md)

## Goal

An agent that troubleshoots your lab using read-only device tools, where every model call and tool call is durable.

## Understand it first

*About 3 minutes.*

An **agent** is an LLM in a loop: it looks at the goal, decides to call a tool, sees the result, decides the next step, and stops when it has an answer. Agents are powerful for troubleshooting, where the next question depends on the last answer. They're also fragile in ordinary code: long-running, many external calls, any of which can fail. Temporal makes them **durable**.

**The loop, mapped onto Temporal:**

```
workflow (deterministic loop)                activities (the outside world)
  messages = [question]
  repeat up to max_turns:
     reply = llm_step(messages, tools)  ───▶  call the model
     if reply has no tool calls: return answer
     for each tool call, in parallel:  ───▶  get_interfaces / get_lldp / get_logging …
     append results to messages
```

The **workflow** owns the loop, the conversation state and the limits. Every **model call** and every **tool call** is an activity. That one split gives you:

- **Crash recovery mid-investigation.** Kill the worker after turn 2: the replay hands back turns 1–2 from history without re-calling the model or the devices, then continues with turn 3.
- **Retries per step.** A rate-limited model call retries without restarting the investigation. A device timeout retries just that tool.
- **A complete audit log.** Every model reply and every tool call with its arguments and result is an event in history. You can see exactly why the agent concluded what it did.
- **Long waits for free.** An agent can pause for a human (tomorrow) for hours, holding no resources.

**Tools are activities you already have.** The troubleshooting tools are the read-only device activities from Weeks 1–3. A tool definition is just an activity plus a JSON schema the model can read: name, description, parameters. Write descriptions for the model as you would for a new colleague: what the tool returns, and when it's useful.

**Tool failures go back to the model.** If `get_interfaces` fails on a device, the agent loop catches the error and returns it to the model as a tool result marked as an error, rather than failing the workflow. Models handle that well: they try another device or tool, as a human would.

**Two ways to build it:**

1. **Hand-written loop** (the main solution): about 50 lines that make every moving part visible: the message list, the tool calls, the limits. It's the best way to understand what a durable agent really is, and it works with any model API.
2. **Framework integration:** Temporal's **OpenAI Agents SDK** integration (generally available) wires the same structure for you. You register `OpenAIAgentsPlugin` on the client and worker, and wrap activities as tools with `activity_as_tool`; model calls automatically become activities. There are experimental plugins for Google ADK, Strands, LangGraph and others. The solution includes an Agents SDK variant to compare.

Either way, the principle is the same: **the agent's control flow is durable workflow code; everything non-deterministic is an activity.**

**Read-only by construction.** Today's agent can look but not touch: its tool list contains only `show`-style activities. That isn't a prompt instruction the model might ignore. The workflow simply has no way to call a config-changing activity. Making changes is tomorrow's job, behind a human approval.

**Watch the history size.** Each turn adds the growing message list to history. For long investigations, cap turns (you will), keep tool outputs concise, and for production-scale agents look at continue-as-new between investigations or External Payload Storage for large payloads.

**What you'll practise today:** shutting an interface in the lab, asking the agent why two devices can't reach each other, reading its investigation turn by turn in the UI, and killing the worker mid-investigation to watch it resume.

## Learn

- The agent loop (model decides → tool runs → repeat) maps cleanly onto Temporal: the loop is the workflow; each model call and tool call is an activity.
- Temporal's **OpenAI Agents SDK integration** does this wiring for you. Experimental plugins exist for Google ADK, Strands, LangGraph, Deep Agents and others.
- Docs: [OpenAI Agents integration](https://docs.temporal.io/develop/python/integrations/openai-agents) · [All integrations](https://docs.temporal.io/develop/python/integrations)

## Build

```bash
uv add temporalio-openai-agents
```

```python
# client and worker
client = await Client.connect(TEMPORAL_ADDRESS, plugins=[
    OpenAIAgentsPlugin(model_params=ModelActivityParameters(start_to_close_timeout=timedelta(seconds=60)))
])

# workflow
@workflow.defn
class TroubleshootingAgentWorkflow:
    @workflow.run
    async def run(self, question: str) -> str:
        agent = Agent(
            name="NetOps troubleshooter",
            instructions="You diagnose Arista EOS issues. Use tools; never guess device state.",
            tools=[
                activity_as_tool(get_interfaces, start_to_close_timeout=timedelta(seconds=30)),
                activity_as_tool(get_bgp_summary, start_to_close_timeout=timedelta(seconds=30)),
                activity_as_tool(get_lldp_neighbors, start_to_close_timeout=timedelta(seconds=30)),
                activity_as_tool(get_logging, start_to_close_timeout=timedelta(seconds=30)),
            ],
        )
        result = await Runner.run(agent, question)
        return result.final_output
```

Register the tool activities on the worker as usual. Check the integration page for the exact import paths on your installed version.

**Not on OpenAI?** The Agents SDK can use other providers through its model-provider options; or skip the framework and hand-write the loop as a workflow calling an `llm_step` activity and tool activities — a good exercise either way.

## Exercise

`shutdown` `Ethernet1` on `bos-acc-01`, then ask: *"Why can't bos-acc-01 reach nyc-rtr-01?"* Read the history: every tool call is an event.

## Rule

Tools in this workflow are **read-only**. Changes go through Day 27.

## Done when

- [ ] The agent finds the shut interface, and killing the worker mid-investigation resumes where it left off.

## Solution

Try it yourself first, then compare: [solutions/day26](../../../solutions/day26/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
