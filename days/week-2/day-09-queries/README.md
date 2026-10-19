# Day 09 — Queries

[← Day 08](../day-08-signals/README.md) · [Day 10 →](../day-10-updates/README.md)

## Goal

Ask a running workflow what it knows, without changing it.

## Understand it first

*About 3 minutes.*

Signals push information **in**. Queries pull it **out**: "what's your status right now?" They're what turns a running workflow into something you can monitor and build tools on.

**A query is a read-only method on the workflow:**

```python
@workflow.query
def get_status(self) -> WatchStatus:
    return WatchStatus(device=self.device, paused=self.paused, checks=self.checks, ...)
```

The caller (UI, CLI, Python) asks the server; the server forwards the query to a worker; the worker runs the method against the workflow's current in-memory state and returns the answer.

**Queries don't touch history.** Unlike signals and updates, a query writes nothing to the event history. That's what makes them cheap and safe to call as often as you like, from a dashboard refreshing every few seconds for example. The flip side is the strict rules about what a query handler may do:

- **No state changes.** The query isn't recorded, so a mutation would be lost on replay. State and history would disagree.
- **No awaiting:** no activities, no timers, no `wait_condition`. A query answers immediately from memory.
- **Return something serializable**, like a pydantic model. It goes through the data converter like everything else.

**How a worker answers a query for a workflow it doesn't have in memory:** workers cache recently active workflows. If the query hits a worker without that workflow cached, the worker **replays the history** to rebuild state, then answers. So queries work even after a worker restart, and they work on **completed** workflows too, as long as some worker for that task queue is running.

**Design queries as your workflow's API.** For the orchestrator, `get_drift()` and `get_state()` are how humans and tools will learn what's going on: a CLI, a Slack bot, or a Grafana panel backed by a tiny exporter. Return structured models, not strings, so tools can consume them.

**Queries vs visibility.** There are two ways to answer "what's going on?":

| | Query | Visibility (list/search) |
| --- | --- | --- |
| Asks | One workflow, directly | The server's index of all workflows |
| Freshness | Exact, current state | Eventually consistent (usually sub-second) |
| Cost | Needs a worker; may trigger a replay | Cheap, indexed, no worker needed |
| Example | "What's drifted on the orchestrator right now?" | "Which workflows are running? Which have `ComplianceState=drifted`?" |

Today's `status` command combines them: `client.list_workflows(...)` (visibility) finds all the running watch workflows, then a query to each gets their detailed state. On Day 20 you'll add custom **search attributes**, so visibility alone can answer questions like "which devices in BOS are drifted" without querying anything.

**The UI's Queries tab** calls these methods for you, including the built-in `__stack_trace` query, which shows where each coroutine in the workflow is currently waiting. It's surprisingly useful when a workflow seems stuck: you can see that it's blocked in `wait_condition(lambda: not self.paused)`, and realise someone left it paused.

**Typical mistake to avoid:** writing a query that "helpfully" resets a counter or clears a flag. It will appear to work, until the next replay quietly undoes it. If calling it should change something, it's a signal or an update, not a query.

**What you'll practise today:** a `get_status` query returning a rich model, calling it from the UI, the CLI and Python, and a small tool that lists every watch and prints its status. That's the start of your operational tooling.

## Build

```python
class WatchStatus(BaseModel):
    device: str
    paused: bool
    checks: int
    last_checked: datetime | None
    last_facts: DeviceFacts | None

@workflow.query
def get_status(self) -> WatchStatus:
    return WatchStatus(device=self.device, paused=self.paused, checks=self.checks,
                       last_checked=self.last_checked, last_facts=self.last_facts)
```

Set `self.last_checked = workflow.now()` after each check.

- UI: open the workflow → **Queries** tab → `get_status`.
- CLI: `temporal workflow query --workflow-id watch-bos-rtr-01 --type get_status`
- Python: `await handle.query(DeviceWatchWorkflow.get_status)`

## Gotchas

- Query handlers must not mutate state, await activities, or sleep.
- Queries work on completed workflows too (as long as a worker for that type is running).
- Queries don't appear in history. Signals and updates do.

## Done when

- [ ] A small `starters/status.py` prints the status of every watch workflow (`client.list_workflows('WorkflowType="DeviceWatchWorkflow"')`).

## Solution

Try it yourself first, then compare: [solutions/day09](../../../solutions/day09/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
