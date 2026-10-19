# Day 01 — Lab up, repo tour

[← Week 1](../README.md) · [Day 02 →](../day-02-eapi-activity/README.md)

## Goal

Temporal server, UI, worker and client all running, and you can read an event history from the CLI.

## Understand it first

*About 3 minutes.*

Temporal is easiest to understand as **a control plane for your code**. If you've worked with network control planes, the split will feel familiar.

**The server is the control plane.** It doesn't run your code. It stores, for every workflow, an ordered **event history**: "workflow started with input X", "activity A scheduled", "activity A completed with result Y", "timer fired". That history is the source of truth. It lives in a database (SQLite in your dev server, PostgreSQL or Cassandra in production) and survives anything that happens to your Python processes.

**Workers are the data plane.** A worker is a Python process you write and run. It connects *out* to the server and long-polls a **task queue**: "give me work for `netops-orchestration`". Nothing connects in to the worker, which is why workers are easy to run in containers, behind NAT, or in OpenShift with no Service or Route.

**Workflows and activities are the two kinds of code a worker runs.**

- A **workflow** is the decision-maker: "get the device list, check each device, if it's drifted start a remediation". It must be **deterministic**: run twice with the same history, it makes the same decisions in the same order. That rule is what lets Temporal recover it anywhere (Day 4).
- An **activity** is anything that touches the outside world: an eAPI call, a Nautobot query, writing a file, calling an LLM. Activities can fail, time out and be retried. The workflow just sees "it eventually returned X" or "it failed for good".

```
 your starter ──start──▶  Temporal server  ◀──poll──  your worker
                         (history + queues)            ├─ workflow code (decides)
                                                       └─ activity code (does I/O)
```

**How one workflow actually runs:**

1. Your starter asks the server to start `HelloWorkflow("Manny")` on queue `netops-orchestration`. The server writes `WorkflowExecutionStarted` and puts a **workflow task** on the queue.
2. A worker picks it up and runs your workflow code until it hits something it must wait for: here, `execute_activity(say_hello)`. The code doesn't call the activity directly. It returns a **command** to the server: "please schedule `say_hello`".
3. The server records `ActivityTaskScheduled` and puts an **activity task** on the queue. Some worker, maybe a different one, runs `say_hello` and reports the result. The server records `ActivityTaskCompleted`.
4. A new workflow task wakes the workflow up with the result, and the code continues to the end.

Notice what this buys you: **no step depends on a particular process staying alive.** If the worker dies between steps 3 and 4, another worker picks up the next workflow task. It rebuilds the workflow's state by **replaying** the history through your code, then carries on. That's the whole trick behind "durable execution", and the rest of the month is variations on it.

**Task queues are just names.** They're created on first use; there's nothing to configure. They let you route work: later you'll put device I/O on its own queue so only certain workers, with network access to the switches, run it (Day 21).

**The UI and CLI are windows into history.** Every page in the Temporal UI is rendered from the event history. Learning to read a history is the single most valuable operator skill. When something goes wrong at 2 a.m., the history tells you exactly what happened, in order, with inputs and errors.

**Why your dev server needs `--db-filename`:** by default `temporal server start-dev` keeps everything in memory. That's fine for a hello-world, but this course builds workflows that run for days. A file-backed database means a container restart doesn't wipe them.

By the end of today you should be able to look at any event in a history and say who produced it: the client, the server, or a worker.

## Learn

- The split: **Workflow** (deterministic decisions) · **Activity** (any I/O) · **Worker** (your process that runs both) · **Task Queue** (how the server hands work to workers).
- The server stores the **event history**; your worker holds no durable state. Kill it any time.
- Docs: [Workflow basics](https://docs.temporal.io/develop/python/workflows/basics) · [Run a worker](https://docs.temporal.io/develop/python/workers/run-worker-process)

## Build

1. `./lab/start-temporal.sh` and open http://localhost:8233.
2. `cp .env.example .env` and `uv sync`.
3. Terminal 1: `uv run --env-file .env python -m netops_temporal.workers.main`
4. Terminal 2: `uv run --env-file .env python -m netops_temporal.starters.hello Manny`
5. Read `src/netops_temporal/` top to bottom. Note the two task queue names in `constants.py`.

## CLI to learn today

```bash
temporal workflow list
temporal workflow describe --workflow-id hello-manny
temporal workflow show --workflow-id hello-manny          # the event history
temporal workflow show --workflow-id hello-manny -o json  # what replay tests use (Day 6)
```

No CLI on your Mac? `podman exec -it temporal-dev temporal workflow list --address localhost:7233`.

## Break it

- Stop the worker. Start a workflow. Watch it sit in **Running** with a pending workflow task.
- Start the worker again and watch it complete. Nothing was lost.
- `podman restart temporal-dev`, then refresh the UI: your history is still there (that's `--db-filename`).

## Done when

- [ ] You can name each event in `HelloWorkflow`'s history and say who produced it (client, server, worker).
- [ ] `uv run pytest` passes.

## Solution

Try it yourself first, then compare: [solutions/day01](../../../solutions/day01/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
