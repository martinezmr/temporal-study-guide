# Day 04 — Determinism and the sandbox

[← Day 03](../day-03-models-and-failures/README.md) · [Day 05 →](../day-05-heartbeats-and-threads/README.md)

## Goal

Understand replay well enough to never be surprised by a non-determinism error in CI/CD.

## Understand it first

*About 3 minutes.*

Today is the most important concept in Temporal, and the one behind most production incidents: **replay and determinism**.

**Why replay exists.** On Day 1 you saw that a workflow survives a worker crash because another worker rebuilds its state. But Temporal doesn't store your workflow's variables. It stores **events**. To rebuild state, the new worker re-runs your workflow function from the top, feeding it results from history instead of really executing anything:

```
History:  started(bos-rtr-01) → activity get_facts scheduled → completed {version: 4.32.0F} → timer 60s started …

Replay:   run("bos-rtr-01")
            execute_activity(get_facts)  → SDK: "history says this happened, here's the result"  (no network call)
            sleep(60)                    → SDK: "history says this timer started; still pending" → wait for real
```

Replay is fast because activities aren't re-executed; their recorded results are handed back. When the code reaches the point where history ends, it continues live.

**The determinism rule.** For replay to work, your workflow code must produce **the same sequence of commands** (schedule activity, start timer, start child, and so on) every time it runs against the same history. If the new code asks for something different from what history recorded at that point, the SDK can't reconcile them and raises a **non-determinism error**.

Things that break determinism:

- **Reading the clock:** `datetime.now()` returns a different value on replay. Use `workflow.now()`, which returns the time recorded for the current workflow task.
- **Randomness and UUIDs:** `random`, `uuid.uuid4()`. Use `workflow.random()` and `workflow.uuid4()`, which are seeded from history.
- **I/O of any kind** in workflow code: network, files, env vars that might change. Move it into an activity.
- **Changing code** for workflows that are already running: reordering activities, adding a step before an existing one, removing a timer. This is the one that bites in CI/CD, and Day 19 is entirely about doing it safely.

**The sandbox helps.** The Python SDK runs workflow code in a sandbox that intercepts many non-deterministic calls (`datetime.now()`, file access) and fails fast with `RestrictedWorkflowAccessError`. It's a safety net, not a guarantee: it can't catch a logic change between deployments. That's what replay tests are for (Day 6).

**What a non-determinism error looks like operationally.** It fails the **workflow task**, not the workflow. The workflow sits there, still "Running", with a task retrying every few seconds and the error in the worker log. Nothing is lost; it's waiting for code that can replay its history. Your options are to roll back the deploy, ship a version-aware fix (Day 19), reset the workflow to an earlier point, or terminate it. Retrying won't help.

**`imports_passed_through()`** — you've seen it in every workflow file. The sandbox normally re-imports modules for isolation, which is slow and can trip on third-party libraries. Wrapping your activity and model imports in `with workflow.unsafe.imports_passed_through():` tells the sandbox to share them. That's safe because your workflow only uses those modules for function references and data classes, not for side effects.

**Why `workflow.logger`?** On replay, your code re-runs, so a normal `print` or logger would emit duplicate lines every time a worker rebuilt the workflow. `workflow.logger` knows when it's replaying and stays quiet.

**A useful mindset:** think of workflow code as a **recipe** that Temporal can re-read from the top at any moment. Every line must give the same instruction every time. Anything that can vary (time, randomness, the outside world) either comes from a `workflow.*` API or from an activity's recorded result.

## Learn

- When a worker picks up a workflow, it **replays** the history through your code. The code must make the same decisions in the same order.
- Safe replacements: `workflow.now()`, `workflow.random()`, `workflow.uuid4()`, `workflow.logger`, `workflow.sleep()`.
- The Python sandbox re-imports modules per workflow and blocks many non-deterministic calls. `workflow.unsafe.imports_passed_through()` is for importing your activity/model modules without that cost.
- Docs: [Python sandbox](https://docs.temporal.io/develop/python/best-practices/python-sdk-sandbox)

## Build

Add a branch to `GetFactsWorkflow`:

```python
if workflow.now().hour < 6:
    workflow.logger.info("Inside quiet hours, collecting extended facts")
    # call an extra activity, e.g. get_inventory
```

## Break it (the important part)

1. Change `workflow.now()` to `datetime.now()`. Start the workflow. What does the sandbox do?
2. Undo that. Start a workflow that sleeps 60 s (`await workflow.sleep(60)`) between two activities.
3. While it sleeps, stop the worker, **swap the order of the two activities**, start the worker.
4. Read the non-determinism error in the UI and worker log. This is exactly what an unsafe deploy looks like.
5. Terminate it: `temporal workflow terminate --workflow-id ...`.

## Done when

- [ ] You can list three things that must never happen in workflow code.
- [ ] You've seen a non-determinism error and know it is fixed by versioning (Day 19), not by retrying.

## Solution

Try it yourself first, then compare: [solutions/day04](../../../solutions/day04/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
