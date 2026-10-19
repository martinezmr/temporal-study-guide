# Solutions

Worked solutions for every day of the guide. **Try the day yourself first**, then compare.

## Layout

```
solutions/
  shared/            # code every day reuses
    settings.py      #   env-driven settings (DEVICE_MODE defaults to "mock")
    models.py        #   pydantic models
    mock_lab.py      #   in-memory stand-in for your 4 cEOS nodes + Nautobot intent
    eapi.py          #   real eAPI client (async + sync) that falls back to mock_lab
    nautobot.py      #   GraphQL intent, or mock
    activities.py    #   every activity used in the course
    drift_cycle.py   #   "collect intent + state + diff" helper (Days 15+)
    llm.py           #   Anthropic Messages API over HTTPS (Days 25+)
    nexus_setup.py   #   create Nexus endpoints from Python
    runner.py        #   connect() with the pydantic converter, make_worker()
  netops_contracts/  # Day 24: the Nexus contract as its own package
  day01 ... day30/   # SOLUTION.md + workflows.py + run.py for each day
  tests/             # pytest suite: one file per day (or group of days)
```

## Mock mode vs live mode

Everything defaults to **`DEVICE_MODE=mock`**: an in-memory lab with your four device names, your topology, and two built-in drifts (bos-acc-01 is missing NTP; nyc-rtr-01 is on 4.31.2F instead of 4.32.0F). Mock mode needs no containerlab, Nautobot or API keys, so every demo and test runs anywhere.

To use your real lab:

```bash
DEVICE_MODE=live uv run --env-file .env python -m solutions.day07.run demo
```

With `ANTHROPIC_API_KEY` set, Days 25–29 call a real model; without it they use deterministic mocks.

## Running

Most days have a `demo` command that starts a worker in-process, runs the scenario, and prints the result. You need the Temporal dev server running (`./lab/start-temporal.sh`):

```bash
uv run python -m solutions.day02.run demo bos-rtr-01
uv run python -m solutions.day14.run worker      # long-running days: worker in one terminal...
uv run python -m solutions.day14.run start       # ...commands in another
```

Each `SOLUTION.md` lists that day's exact commands and explains the choices.

## Tests

```bash
uv run pytest solutions/tests -q                  # everything
uv run pytest solutions/tests/test_day17.py -v    # one day
```

Most tests use Temporal's time-skipping test server, so a 4-hour approval timeout takes milliseconds. Tests for updates, Nexus and search attributes use `WorkflowEnvironment.start_local()`, a real dev server that the SDK downloads on first use. Neither needs your `temporal-dev` container.

## Status

These solutions were written against temporalio 1.34 docs but **could not be executed where they were written** (no package access there). Run `uv run pytest solutions/tests` first. If anything fails, the failure message plus the day's `SOLUTION.md` is usually enough to fix it, or paste the output to Claude. The files marked "untested" (`day26/agents_sdk_variant.py`, `day28/agents_sdk_mcp_variant.py`) need the extra `temporalio-openai-agents` package and an OpenAI-compatible key.
