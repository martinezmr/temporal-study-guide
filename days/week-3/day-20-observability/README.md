# Day 20 — Observability

[← Day 19](../day-19-versioning/README.md) · [Day 21 →](../day-21-production-workers/README.md)

## Goal

Find any device's compliance story in the UI in seconds, and see your workers' health in Grafana.

## Understand it first

*About 3 minutes.*

A system you can't see into is a system you can't operate. Today is about making your workflows **findable**, **readable** and **measurable**, so that at 2 a.m. you can answer "what's wrong with nyc-rtr-01?" in seconds.

**Three questions, three tools.**

1. *"Which workflows are about X?"* → **search attributes** (indexed, queryable).
2. *"What is this workflow, in plain words?"* → **user metadata** (static summary and details shown in the UI) and **memos**.
3. *"How healthy is the system overall?"* → **metrics** and **traces**.

Logs cut across all three.

**Search attributes: an index over your workflows.** Out of the box you can filter by workflow type, status and start time. Custom search attributes add your own indexed fields, like `DeviceName`, `Site` and `ComplianceState`:

```bash
temporal operator search-attribute create --name ComplianceState --type Keyword
```

Set them when starting a workflow (`search_attributes=...`), and change them as the workflow learns more:

```python
workflow.upsert_search_attributes([COMPLIANCE_STATE.value_set("drifted")])
```

Then, in the UI's filter box or from code:

```
ComplianceState = "drifted" AND Site = "bos"
WorkflowType = "DeviceUpgradeWorkflow" AND ExecutionStatus = "Running"
```

They're the visibility half of Day 9's table. They answer fleet-wide questions without querying every workflow. Two gotchas: attributes must be **registered per namespace** before use (upserting an unregistered one fails the workflow task), and they're **indexed metadata, not storage**, so keep them small: IDs, states, sites.

**User metadata: make the UI readable.** `static_summary` (one line) and `static_details` (more text), set when starting a workflow or child, appear in the workflow list and detail page. A list reading "Remediate bos-acc-01: missing NTP (low risk)" is far easier to scan than a column of IDs. On Day 29 the LLM's explanation becomes each child's summary. A **memo** is similar unindexed key-value data attached to the workflow.

**Logs that respect replay.** `workflow.logger` adds workflow context to each line and **stays quiet during replay**, so a workflow rebuilt ten times logs each message once. `activity.logger` adds activity context. Ship worker logs wherever you ship container logs. In OpenShift that's your cluster logging stack.

**Metrics: the fleet's vital signs.** The SDK can expose Prometheus metrics from each worker:

```python
Runtime(telemetry=TelemetryConfig(metrics=PrometheusConfig(bind_address="0.0.0.0:9000")))
```

The ones to watch first:

- **Schedule-to-start latency:** how long tasks wait before a worker picks them up. Rising means workers can't keep up, so scale out.
- **Activity failures** by activity type: a spike in `get_running_config` failures usually means a device or network problem.
- **Workflow task failures:** non-determinism or bugs, often right after a deploy.
- **Worker slots in use:** are you hitting `max_concurrent_activities`?

The Temporal server exposes its own metrics too. Grafana dashboards for both are a few containers away.

**Tracing.** The OpenTelemetry interceptor (`temporalio.contrib.opentelemetry`) propagates trace context from client to workflow to activities, so one trace shows "API call → start orchestrator cycle → 12 device activities", with timings. That's useful once several services call into Temporal.

**Interceptors** are the general mechanism behind tracing: hooks that wrap every client call, workflow and activity. You can use them for custom logging, auth headers or metrics. You won't need to write one this month, but know they exist.

**What you'll practise today:** registering three search attributes, a sweep that tags each device's check workflow with them and a readable summary, finding "drifted devices in BOS" in one query, and exposing worker metrics for Prometheus.

## Learn

- Replay-safe logging: `workflow.logger` (suppressed during replay), `activity.logger`.
- **Search attributes** — indexed fields you filter on. **Memo** — unindexed notes. **User metadata** — a static summary/details shown in the UI.
- SDK metrics (Prometheus) and OpenTelemetry tracing via interceptors.
- Docs: [Observability](https://docs.temporal.io/develop/python/platform/observability) · [Enriching the UI](https://docs.temporal.io/develop/python/platform/enriching-ui) · [Interceptors](https://docs.temporal.io/develop/python/workers/interceptors)

## Build

1. Register attributes:

    ```bash
    temporal operator search-attribute create --name DeviceName --type Keyword
    temporal operator search-attribute create --name Site --type Keyword
    temporal operator search-attribute create --name ComplianceState --type Keyword
    ```

2. Set them when starting children and update them as state changes:

    ```python
    DEVICE = SearchAttributeKey.for_keyword("DeviceName")
    STATE = SearchAttributeKey.for_keyword("ComplianceState")
    workflow.upsert_search_attributes([STATE.value_set("remediating")])
    ```

3. Give children a summary: `start_child_workflow(..., static_summary=f"Remediate {device}: {len(diff)} lines")`.
4. In the UI: `ComplianceState = "drifted" AND Site = "bos"`.

## Optional: metrics

```python
runtime = Runtime(telemetry=TelemetryConfig(metrics=PrometheusConfig(bind_address="0.0.0.0:9000")))
client = await Client.connect(TEMPORAL_ADDRESS, runtime=runtime)
```

Add Prometheus + Grafana containers scraping `:9000`. Watch `temporal_activity_execution_failed` and schedule-to-start latency.

## Done when

- [ ] You can find every remediation for `nyc-rtr-01` this week with one UI query.

## Solution

Try it yourself first, then compare: [solutions/day20](../../../solutions/day20/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
