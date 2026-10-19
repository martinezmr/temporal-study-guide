# Day 20 — Solution

**Files:**

- `search_attributes.py`: typed keys.
- `setup_search_attributes.sh`: registers the attributes.
- `workflows.py`: a sweep starts one child per device, each with `DeviceName`/`Site` set at start, a `static_summary`, and `ComplianceState` upserted as it learns more.
- `run.py --metrics`: Prometheus metrics.

```bash
bash solutions/day20/setup_search_attributes.sh
uv run python -m solutions.day20.run worker --metrics
uv run python -m solutions.day20.run sweep
uv run python -m solutions.day20.run find 'ComplianceState = "drifted" AND Site = "bos"'
curl -s localhost:9000/metrics | grep temporal_activity
uv run pytest solutions/tests/test_day20.py
```

In the UI, paste the same query into the workflow list filter.

## Which tool for what

| Need | Use |
| --- | --- |
| Filter and find workflows | **Search attributes** (indexed): `DeviceName`, `Site`, `ComplianceState` |
| Human-readable label in the list and detail page | **`static_summary` / `static_details`** at start |
| Extra unindexed context | **Memo** |
| What happened, in order | **`workflow.logger` / `activity.logger`**. Workflow logs are suppressed during replay, so no duplicates |
| Rates, latencies, failures | **SDK metrics** → Prometheus/Grafana. Watch schedule-to-start latency (are workers keeping up?) and activity failures |
| One trace across client → workflow → activity | **OpenTelemetry** via `temporalio.contrib.opentelemetry.TracingInterceptor` on client and worker |

## Gotcha

Upserting an unregistered search attribute fails the workflow task. Run the setup script against each namespace first.
