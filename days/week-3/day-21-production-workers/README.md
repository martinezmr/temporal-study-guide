# Day 21 — Production-shaped workers

[← Day 20](../day-20-observability/README.md) · [Week 4 →](../../week-4/README.md)

## Goal

Workers you'd be comfortable running in OpenShift: split by job, gentle on devices, no secrets in history, packaged as a container.

## Understand it first

*About 3 minutes.*

So far one worker process has run everything. Before OpenShift, you'll reshape it the way it should run in production: **split by job, gentle on the network, safe with secrets, and packaged as a container.**

**Split workers with task-queue routing.** A task queue is just a name, and an activity runs on whichever queue the workflow names:

```python
await workflow.execute_activity(get_running_config, d, task_queue="netops-device-io", ...)
```

That lets you run two kinds of worker:

| Worker | Polls | Runs | Needs |
| --- | --- | --- | --- |
| **orchestration** | `netops-orchestration` | Workflow code only | Access to Temporal. Little CPU, no device access |
| **device-io** | `netops-device-io` | Device, Nautobot and LLM activities | Access to Temporal, device management networks and APIs |

Why bother? You **scale them separately** (device I/O is the bottleneck), you **limit them separately** (next section), and only device-io pods need a network path to your switches, which is easy to enforce with a NetworkPolicy on Day 30. Workflow code and its histories never sit next to device credentials.

**Protect the devices.** Automation can hurt a network by being too eager: 400 concurrent eAPI sessions will upset control-plane CPUs. Two layers of throttling:

- **`max_concurrent_activities`** (per worker process): this pod runs at most N activities at once.
- **`max_task_queue_activities_per_second`** (per task queue, **enforced by the server across all workers**): the whole fleet starts at most N device activities per second, however many pods you scale to.

The second one is the important one. You can add pods for resilience without multiplying the load on the switches.

**Graceful shutdown.** OpenShift stops pods by sending SIGTERM, waiting `terminationGracePeriodSeconds`, then killing them. A worker should, on SIGTERM, stop polling for new tasks and let running activities finish within `graceful_shutdown_timeout`. Activities that don't finish in time are retried elsewhere, so nothing is lost either way, but a clean drain avoids half-sent commands and noisy retries. Set the pod's grace period a little longer than the worker's timeout.

**Secrets never enter history.** Everything a workflow passes to an activity is stored in history in plain text, unless encrypted, and visible to anyone with UI access. So credentials must **never** be workflow inputs or activity arguments. Activities read `DEVICE_PASSWORD`, `NAUTOBOT_TOKEN` and the LLM key from their own environment, injected from OpenShift Secrets. Workflows pass device *names*, never passwords.

**Payload encryption, when the data itself is sensitive.** Running configs can contain sensitive material. A **payload codec** encrypts every payload before it leaves the client or worker, so the server stores ciphertext. Every client and worker needs the same codec. The UI then shows encrypted blobs unless you run a codec server that decrypts for authorized users. It's worth it for production; optional for the lab.

**Containerizing for OpenShift.** One image runs every role, chosen by argument (`orchestration` or `device-io`). OpenShift-specific details:

- OpenShift runs containers as a **random UID in group 0**, so make the app directory group-owned by 0 and group-writable (`chgrp -R 0 /app && chmod -R g=u /app`).
- Install dependencies from the lockfile (`uv sync --frozen`) so the image matches what you tested.
- Bake the git SHA in as `BUILD_ID`. It becomes the worker's version on Day 30.

**Workers connect out.** They need egress to Temporal's frontend (gRPC 7233) and, for device-io, to devices and APIs. Nothing connects in: no Service, no Route. That simplifies security reviews considerably.

**What you'll practise today:** splitting into two workers, adding rate limits, handling SIGTERM cleanly, building the image, running the device-io container on the `clab` network, and grepping a history to prove no secret is in it.

## Learn

- Route work by task queue: workflows on `netops-orchestration`, device I/O on `netops-device-io`. Scale and limit them separately.
- Protect devices: `max_concurrent_activities` per worker, `max_task_queue_activities_per_second` across all workers on a queue.
- Payload codecs encrypt payloads before they reach the server.
- Docs: [Workers](https://docs.temporal.io/develop/python/workers) · [Payload encryption](https://docs.temporal.io/develop/python/data-handling/data-encryption)

## Build

1. Split `workers/main.py` into `workers/orchestration.py` (workflows) and `workers/device_io.py` (activities). Pass `task_queue=DEVICE_IO_TASK_QUEUE` on device activity calls.
2. Device worker: `max_concurrent_activities=4`, `max_task_queue_activities_per_second=2.0`.
3. Credentials only from env vars inside activities — never in workflow inputs (they'd be stored in history).
4. Graceful shutdown: handle SIGTERM → `await worker.shutdown()`; set `graceful_shutdown_timeout`.
5. `Containerfile`:

    ```dockerfile
    FROM python:3.13-slim
    COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
    WORKDIR /app
    COPY pyproject.toml uv.lock ./
    RUN uv sync --frozen --no-dev --no-install-project
    COPY src ./src
    RUN uv sync --frozen --no-dev
    ARG BUILD_ID=dev
    ENV BUILD_ID=$BUILD_ID PATH="/app/.venv/bin:$PATH"
    # OpenShift runs as a random UID in group 0
    RUN chgrp -R 0 /app && chmod -R g=u /app
    USER 1001
    ENTRYPOINT ["python", "-m"]
    CMD ["netops_temporal.workers.orchestration"]
    ```

6. Run it on the `clab` network so it reaches the devices:

    ```bash
    podman build -t netops-worker --build-arg BUILD_ID=$(git rev-parse --short HEAD) .
    podman run --rm --network clab --env-file .env netops-worker netops_temporal.workers.device_io
    ```

## Break it

`podman stop` the device worker mid-activity. It should finish or hand back the activity cleanly, and another worker picks it up.

## Done when

- [ ] Two containers (orchestration, device-io) run the whole system.
- [ ] `grep -r password` over a workflow's exported history finds nothing.

## Solution

Try it yourself first, then compare: [solutions/day21](../../../solutions/day21/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
