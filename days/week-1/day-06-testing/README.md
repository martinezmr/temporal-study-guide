# Day 06 — Testing

[← Day 05](../day-05-heartbeats-and-threads/README.md) · [Day 07 →](../day-07-parallel-backup/README.md)

## Goal

Fast tests with no lab, plus a replay test that will become your CI gate.

## Understand it first

*About 3 minutes.*

Temporal code is unusually testable, because the hard parts (timers, retries, crashes) are handled by a server you can run in-process with a fake clock. Today you build three kinds of test, and by Day 30 one of them gates every deploy.

**1. Workflow tests with a time-skipping server.** `WorkflowEnvironment.start_time_skipping()` starts a lightweight test server inside your test. You run a real `Worker` against it, start workflows with a real client, and assert on results. The time skipping is the magic part: whenever your test is waiting on a workflow result and nothing else is happening, the server **jumps the clock to the next timer**. A workflow that sleeps until tomorrow's 02:00 maintenance window completes in milliseconds. This is how you test Day 11's windows, Day 12's continue-as-new, and Day 27's 4-hour approval timeout.

There's also `WorkflowEnvironment.start_local()`, a full dev server that the SDK downloads once. It runs in real time but supports every feature (updates, Nexus, search attributes). Use time-skipping by default and local when you need a feature the test server lacks.

**2. Mocking activities.** Workflow tests shouldn't need your containerlab. A worker routes activity calls **by name**, so you register a fake under the real name:

```python
@activity.defn(name="get_device_facts")
async def fake_facts(device: str) -> DeviceFacts:
    return DeviceFacts(device=device, model="cEOSLab", version="4.32.0F", hostname=device)
```

Your workflow still calls `get_device_facts`; the test worker runs the fake. Now you can simulate anything: a device that times out twice, a 401, a weird version string. That's how you test the failure paths you'll never reproduce on demand with real hardware.

**3. Activity unit tests.** `ActivityEnvironment` runs one activity function directly, with no server and no worker, but with a real activity context. You can capture heartbeats (`env.on_heartbeat`), pre-set heartbeat details to test resume logic, or trigger cancellation. Use it for activity logic; use mocks for workflow logic.

**4. Replay tests: the CI gate.** This is the one that matters most. A **replayer** takes a saved event history and replays it against your current workflow code, without a server. If the code would make different decisions than the history recorded, it raises `NondeterminismError`. That's exactly the error a running workflow would hit after a bad deploy (Day 4), caught in CI instead of production.

The workflow:

1. Run a workflow for real (lab or staging).
2. Export its history: `temporal workflow show --workflow-id X -o json > tests/histories/x.json`.
3. Commit the file. A test replays it with `Replayer(workflows=[...]).replay_workflow(history)`.
4. Every future PR that changes that workflow must still replay every saved history.

Keep a few histories per workflow type, covering different paths: the happy path, the retry path, the rollback path. Refresh them occasionally from real runs so they reflect what's actually running.

**What makes a good Temporal test suite:**

- Fast: mocked activities and time skipping, so the whole suite runs in seconds with the lab off.
- Covers failure paths: retries exhausted, non-retryable errors, cancellation, timeouts.
- Has replay tests for every workflow type that runs in production.

**Why now?** From Week 2 on, workflows get stateful and long-running, and you can't manually wait three days to check that a timer fires. Tests that skip time are the only practical way to know your orchestrator does the right thing on day 3 of a run.

## Learn

- `WorkflowEnvironment.start_time_skipping()` — an in-process test server where timers jump forward.
- Mock activities by registering a function with the same name: `@activity.defn(name="get_device_facts")`.
- `ActivityEnvironment` — unit-test an activity alone (heartbeats, cancellation).
- `Replayer` — replays a saved history against current code and fails on non-determinism.
- Docs: [Testing](https://docs.temporal.io/develop/python/best-practices/testing-suite)

## Build

1. Mocked activity test:

    ```python
    @activity.defn(name="get_device_facts")
    async def fake_facts(device: str) -> DeviceFacts:
        return DeviceFacts(device=device, model="cEOSLab", version="4.32.0F")

    async def test_get_facts():
        async with await WorkflowEnvironment.start_time_skipping(
            data_converter=pydantic_data_converter) as env:
            async with Worker(env.client, task_queue="t", workflows=[GetFactsWorkflow],
                              activities=[fake_facts]):
                r = await env.client.execute_workflow(GetFactsWorkflow.run, "bos-rtr-01",
                                                      id="t1", task_queue="t")
        assert r.version == "4.32.0F"
    ```

2. Replay test:

    ```bash
    temporal workflow show --workflow-id facts-bos-rtr-01 -o json > tests/histories/get_facts.json
    ```

    ```python
    async def test_replay_get_facts():
        history = WorkflowHistory.from_json("facts", Path("tests/histories/get_facts.json").read_text())
        await Replayer(workflows=[GetFactsWorkflow],
                       data_converter=pydantic_data_converter).replay_workflow(history)
    ```

3. An `ActivityEnvironment` test for `collect_show_tech` that asserts it heartbeats.

## Break it

Reorder activities in `GetFactsWorkflow` and run the replay test. It fails — good. That failure in CI is what saves running workflows on Day 30.

## Done when

- [ ] `uv run pytest` runs in seconds with the lab off.
- [ ] At least one history lives in `tests/histories/`.

## Solution

Try it yourself first, then compare: [solutions/day06](../../../solutions/day06/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
