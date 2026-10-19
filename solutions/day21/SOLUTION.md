# Day 21 — Solution

**Files:**

- `workflows.py`: activities routed to `netops-device-io` with `task_queue=`.
- `workers.py`: two roles, device rate limits, graceful SIGTERM shutdown.
- `codec.py`: optional payload encryption.
- `Containerfile`: OpenShift-friendly image.

```bash
# two terminals
uv run python -m solutions.day21.workers orchestration
uv run python -m solutions.day21.workers device-io
uv run pytest solutions/tests/test_day21.py

# as containers on the containerlab network
podman build -f solutions/day21/Containerfile -t netops-worker --build-arg BUILD_ID=$(git rev-parse --short HEAD) .
podman run -d --name w-orch --env-file .env -e TEMPORAL_ADDRESS=host.containers.internal:7233 netops-worker orchestration
podman run -d --name w-io   --env-file .env -e TEMPORAL_ADDRESS=host.containers.internal:7233 --network clab netops-worker device-io
```

(`host.containers.internal` is Podman's name for your Mac. With OrbStack/Docker use `host.docker.internal`.)

## Knobs and why

| Setting | Value | Why |
| --- | --- | --- |
| `max_concurrent_activities` | 4 | Each device-io pod talks to at most 4 devices at once |
| `max_task_queue_activities_per_second` | 2.0 | Server-enforced across **all** device-io pods. Scale pods without hammering eAPI |
| `graceful_shutdown_timeout` | 30 s | On SIGTERM, stop polling and give running activities 30 s to finish |
| Separate task queues | orchestration / device-io | Scale and limit independently. Only device-io pods need network access to devices (a NetworkPolicy on Day 30) |

## Secrets

Activities read `DEVICE_PASSWORD` and `NAUTOBOT_TOKEN` from the environment **inside the worker**. They never appear in workflow inputs or results, so they never reach history. Check with:

```bash
temporal workflow show --workflow-id <id> -o json | grep -i -E 'password|token' || echo clean
```
