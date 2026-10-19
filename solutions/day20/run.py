"""Day 20.

    bash solutions/day20/setup_search_attributes.sh          # once
    uv run python -m solutions.day20.run worker --metrics     # Prometheus on :9000/metrics
    uv run python -m solutions.day20.run sweep
    uv run python -m solutions.day20.run find 'ComplianceState = "drifted" AND Site = "bos"'
"""

import argparse

from temporalio.runtime import PrometheusConfig, Runtime, TelemetryConfig

from solutions.day20.workflows import TASK_QUEUE, ComplianceSweepWorkflow, DeviceComplianceCheckWorkflow
from solutions.shared.activities import DEVICE_ACTIVITIES
from solutions.shared.runner import connect, make_worker, run


async def main(argv: list[str]) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["worker", "sweep", "find"])
    p.add_argument("query", nargs="?", default='ComplianceState = "drifted"')
    p.add_argument("--metrics", action="store_true")
    a = p.parse_args(argv)

    kwargs = {}
    if a.metrics:
        kwargs["runtime"] = Runtime(telemetry=TelemetryConfig(metrics=PrometheusConfig(bind_address="0.0.0.0:9000")))
    client = await connect(**kwargs)
    if a.cmd == "worker":
        await make_worker(client, TASK_QUEUE, [ComplianceSweepWorkflow, DeviceComplianceCheckWorkflow],
                          DEVICE_ACTIVITIES).run()
    elif a.cmd == "sweep":
        print("drifted:", await client.execute_workflow(ComplianceSweepWorkflow.run, id="d20-sweep",
                                                         task_queue=TASK_QUEUE))
    else:
        async for wf in client.list_workflows(a.query):
            print(f"{wf.id:40} {wf.status.name if wf.status else ''}")


if __name__ == "__main__":
    run(main)
