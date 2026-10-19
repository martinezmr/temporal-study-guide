# Day 06 — Solution

The solution is the test suite. Read these in order:

| File | Shows |
| --- | --- |
| `solutions/tests/helpers.py` | Time-skipping and local environments with the pydantic converter |
| `solutions/tests/test_day06.py` | Mocked activity by name, history export → JSON → replay, `ActivityEnvironment` |
| `solutions/tests/test_day04.py` | Replay catching a real non-deterministic change |
| `solutions/tests/test_day05.py` | Heartbeat assertions with `ActivityEnvironment` |

```bash
uv run pytest solutions/tests -q
uv run pytest solutions/tests/test_day06.py -v
```

## Exporting a real history for CI

```bash
uv run python -m solutions.day02.run demo bos-rtr-01
temporal workflow show --workflow-id d02-facts-bos-rtr-01 -o json > tests/histories/get_facts.json
```

Then in a test:

```python
history = WorkflowHistory.from_json("get_facts", Path("tests/histories/get_facts.json").read_text())
await Replayer(workflows=[GetFactsWorkflow], data_converter=pydantic_data_converter).replay_workflow(history)
```

Commit those JSON files. On Day 30 the pipeline replays every one of them before it deploys.

## Mocking an activity

Register a different function under the **same activity name**:

```python
@activity.defn(name="get_device_facts")
async def fake_facts(device: str) -> DeviceFacts: ...
```

The workflow still calls `get_device_facts`; the worker routes it to the fake.
