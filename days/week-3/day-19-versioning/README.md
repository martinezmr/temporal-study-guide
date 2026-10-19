# Day 19 — Versioning (the CI/CD day)

[← Day 18](../day-18-schedules/README.md) · [Day 20 →](../day-20-observability/README.md)

## Goal

Deploy new workflow code while old workflows are still running, without a single non-determinism error.

## Understand it first

*About 3 minutes.*

This is the day that makes continuous deployment possible. On Day 4 you broke a running workflow by changing its code. In a real system workflows are *always* running: the orchestrator runs forever, and upgrades wait hours for windows. You still need to ship changes every week. **Versioning** is how you change workflow code without breaking the workflows already in flight.

**The problem, precisely.** A running workflow will be replayed by whatever code is deployed when it next wakes up. If the new code would make different decisions at a point the history already covers, replay fails (`NondeterminismError`). Activity code, and anything that runs *after* the current point in history, can change freely. The danger is changing decisions the history already recorded.

**Tool 1: patching**, a branch inside the code.

```python
if workflow.patched("add-lldp-check"):
    neighbors = await workflow.execute_activity(get_lldp, ...)   # new behaviour
```

The first time **new** code reaches this line, `patched()` returns `True` and writes a marker into history. When **old** histories, recorded without the marker, are replayed by the new code, `patched()` returns `False`, so the old path is followed and replay matches. Old workflows finish the old way; new workflows take the new path. One worker runs both.

Patches have a lifecycle, so they don't pile up:

1. `if workflow.patched("x"): new else: old` → deploy, and wait until no workflows started before it are still running.
2. `workflow.deprecate_patch("x")` plus only the new code → deploy.
3. Delete the `deprecate_patch` line.

**Tool 2: Worker Versioning** (GA), which works at the deployment level. Each worker declares which build it is:

```python
deployment_config=WorkerDeploymentConfig(
    version=WorkerDeploymentVersion(deployment_name="netops", build_id=GIT_SHA),
    use_worker_versioning=True, default_versioning_behavior=VersioningBehavior.PINNED)
```

You run the old and new builds **side by side** and tell the server which is current (`temporal worker deployment set-current-version`), optionally ramping a percentage first. Each workflow has a **versioning behaviour**:

- **PINNED:** the workflow runs on the build it started on, start to finish. New code never replays old histories, so the workflow needs no patches at all. The cost: old builds must stay up until their pinned workflows drain.
- **AUTO_UPGRADE:** the workflow moves to the current build at its next workflow task. Good for workflows that live forever, but you're back to needing patches for any change that affects code the history already covers.

**How to choose for your system:**

| Workflow | Lifetime | Behaviour |
| --- | --- | --- |
| `ConfigComplianceWorkflow` | Minutes | PINNED, so no patches needed |
| `DeviceUpgradeWorkflow` | Hours (waits for a window) | PINNED; keep the old build up a day |
| `NetworkComplianceOrchestrator` | Forever | AUTO_UPGRADE + patches, or upgrade at continue-as-new |
| `DeviceEntityWorkflow` | Forever | Same as the orchestrator |

**How this becomes CI/CD.** Day 6's replay tests run on every PR, catching changes that would break existing histories. Worker Versioning lets each deploy add a new build next to the old one, ramp it, promote it, and retire the old one once drained. Day 30 wires both into a pipeline, and the Temporal Worker Controller automates the Kubernetes side.

**The mindset:** before merging any workflow change, ask: "could a workflow that's already running reach this code with a history recorded by the old version?" If yes, it needs a patch, or that workflow needs to be pinned. The replay test answers the question for you; today's test proves it by replaying a v1 history against a patched v2 (passes) and an unpatched v2 (fails).

**What you'll practise today:** the patch lifecycle, a versioned worker, and a real rollout: build a1 serves running workflows while b2 takes new ones, then you promote b2.

## Learn

Two tools, often used together:

- **Patching** — branch inside one workflow type:

    ```python
    if workflow.patched("add-lldp-check"):
        await workflow.execute_activity(get_lldp_neighbors, ...)
    ```

    Later, once no old runs remain: `workflow.deprecate_patch("add-lldp-check")`, then remove it.

- **Worker Versioning** (GA) — each worker build declares a deployment name + build ID; the server routes each workflow to a compatible build.
    - **PINNED** — the workflow finishes on the build it started on. Best for short workflows (compliance, upgrade).
    - **AUTO_UPGRADE** — moves to the current build on its next task. For the long-lived orchestrator; protect changes with patches, or move it at continue-as-new.

- Docs: [Versioning](https://docs.temporal.io/develop/python/workflows/versioning) · [Worker Versioning](https://docs.temporal.io/worker-versioning) · [Configure a worker](https://docs.temporal.io/production-deployment/worker-deployments/worker-versioning/configure-worker)

## Build

```python
worker = Worker(
    client, task_queue=ORCHESTRATION_TASK_QUEUE, workflows=[...], activities=[...],
    deployment_config=WorkerDeploymentConfig(
        version=WorkerDeploymentVersion(deployment_name="netops", build_id=os.environ["BUILD_ID"]),
        use_worker_versioning=True,
        default_versioning_behavior=VersioningBehavior.PINNED,
    ),
)

@workflow.defn(versioning_behavior=VersioningBehavior.AUTO_UPGRADE)
class NetworkComplianceOrchestrator: ...
```

## Practice the rollout

```bash
BUILD_ID=a1 uv run python -m netops_temporal.workers.main   # build A
temporal worker deployment set-current-version --deployment-name netops --build-id a1
# start a few ConfigComplianceWorkflows that sleep
# change ConfigComplianceWorkflow, then:
BUILD_ID=b2 uv run python -m netops_temporal.workers.main   # build B, alongside A
temporal worker deployment set-ramping-version --deployment-name netops --build-id b2 --percentage 25
temporal worker deployment set-current-version --deployment-name netops --build-id b2
temporal worker deployment describe --deployment-name netops
```

Check `temporal worker deployment --help` for exact flags on your CLI version.

## Done when

- [ ] Old pinned runs finished on `a1` while new runs started on `b2` (visible in each run's details).
- [ ] You've written down which of your workflows are PINNED vs AUTO_UPGRADE, and why.

## Solution

Try it yourself first, then compare: [solutions/day19](../../../solutions/day19/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
