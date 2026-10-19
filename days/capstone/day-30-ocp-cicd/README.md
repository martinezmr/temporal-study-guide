# Day 30 — Containers, CI/CD and OpenShift

[← Day 29](../day-29-assemble-orchestrator/README.md) · [Back to start](../../../README.md)

## Goal

Ship a workflow change through a pipeline: replay-tested, deployed as a new build, with running remediations finishing on the old code.

## Understand it first

*About 3 minutes.*

The last day turns the lab into something you could run for real: **workers in OpenShift, deployed by a pipeline, with a gate that prevents breaking running workflows.** The ideas are standard platform engineering, plus one Temporal-specific twist: deploys must respect workflows that are mid-flight.

**What runs where.**

- **Temporal server + UI:** either self-hosted (Temporal's Helm charts with an external PostgreSQL, the UI behind an OpenShift Route, mTLS between workers and the frontend) or **Temporal Cloud**, with only your workers in OCP. Self-hosting means operating a stateful distributed system; Cloud means far less to run. For a single team, Cloud plus workers in OCP is often the pragmatic choice.
- **Workers:** one container image, three Deployments (`orchestration`, `device-io`, `compliance`), each started with its role as an argument. They connect *out* to Temporal, so no Services or Routes are needed for them.

**OpenShift specifics that trip people up:**

- **Arbitrary UIDs.** OpenShift's default security constraints run containers as a random UID in group 0. Images must have group-0-writable app directories (the Day 21 Containerfile handles this).
- **Graceful termination.** Pod `terminationGracePeriodSeconds` must exceed the worker's `graceful_shutdown_timeout`, so in-flight activities can finish on SIGTERM.
- **Secrets** come from OpenShift Secrets as env vars, and never pass through workflow inputs (Day 21).
- **NetworkPolicy:** only device-io and compliance pods get egress to device management networks. Orchestration pods only reach Temporal.

**The pipeline, and why each stage exists:**

1. **Test:** unit and workflow tests in mock mode. Fast, no lab needed.
2. **Replay gate:** replay every exported history in `tests/histories/` against the new commit. This is the Temporal-specific stage. It catches a change that would hit `NondeterminismError` in workflows already running (Day 4, Day 19), **before** it reaches them. A failure here means "add a patch or pin that workflow", not "re-run the job".
3. **Build:** image tagged with the git SHA. The same SHA becomes the worker's `BUILD_ID`.
4. **Deploy with Worker Versioning:** the new build runs **alongside** the old one. Ramp a percentage, then make it current. PINNED workflows (remediations, upgrades) finish on the build they started on; the AUTO_UPGRADE orchestrator moves forward. Once nothing is pinned to the old build, its Deployment is removed.

Step 4 by hand is fiddly, so the **Temporal Worker Controller** (GA) automates it on Kubernetes: you declare the image, and it creates versioned Deployments, ramps, promotes, and retires old builds once drained. Check its fit with your cluster's security constraints before adopting it.

**Keeping the replay gate honest.** It's only as good as the histories you feed it. Export real histories from the lab or staging regularly: happy paths, retries, rollbacks, approvals, timeouts. Commit them. A workflow type with no saved histories isn't protected.

**Operating it day to day:**

- Dashboards: schedule-to-start latency (are workers keeping up?), activity failures by type (device problems), workflow task failures (bad deploys).
- Runbooks: the orchestrator's `get_state` query, the UI search `ComplianceState="drifted"`, and how to pause the orchestrator during a change freeze.
- Upgrades of Temporal itself: follow the server's supported upgrade path, or let Cloud handle it.

**What "done" looks like.** You merge a PR that changes `ConfigComplianceWorkflow`. The pipeline tests it, replays real histories against it, builds and deploys a new worker version, and you watch in-flight remediations finish on the old code while new ones start on the new code, with no downtime and no stuck workflows.

**After today,** you have the skills and the reference implementation for the project you described: an entity orchestrator comparing intent with state, launching upgrades and compliance work, AI where it helps, and continuous delivery of the workers in OpenShift. The next step is pointing it at a real source of truth and a few real devices, read-only first.

## Workers

One image (`Containerfile` from Day 21), three Deployments:

| Deployment | Namespace | Task queue | Runs |
| --- | --- | --- | --- |
| `orchestration-worker` | default | `netops-orchestration` | orchestrator, upgrade, agent workflows |
| `device-io-worker` | default | `netops-device-io` | eAPI / Nautobot / LLM activities |
| `compliance-worker` | compliance | `compliance-tq` | Nexus handler, `ConfigComplianceWorkflow` |

`BUILD_ID` = git SHA, passed as a build arg and used in `WorkerDeploymentVersion`.

## Pipeline

Extend `.github/workflows/ci.yml` (or OpenShift Pipelines/Tekton — same stages):

1. `ruff` + `pytest` (time-skipping, mocked devices).
2. **Replay tests** against `tests/histories/` — fail the build on non-determinism. Refresh histories from staging regularly.
3. Build and push the image (`ghcr.io/<you>/netops-worker:<sha>`).
4. Deploy the new build alongside the old one, ramp, then make it current (Day 19 commands).

Automate step 4 with the [Temporal Worker Controller](https://docs.temporal.io/production-deployment/worker-deployments/kubernetes-controller) (GA): it manages versioned worker Deployments on Kubernetes and retires old builds once their pinned workflows drain. Confirm it fits your OCP security constraints before committing to it.

## Temporal server and UI on OCP

Two options:

- **Self-hosted:** Temporal's Helm charts with an external PostgreSQL, UI exposed via a Route, mTLS between workers and frontend. [Self-hosted guide](https://docs.temporal.io/self-hosted-guide)
- **Temporal Cloud:** run only the workers in OCP. Far less to operate; Nexus endpoints and Worker Versioning work the same.

## OpenShift specifics

- Images run as an arbitrary non-root UID in group 0 (the default restricted SCC) — the Day 21 `Containerfile` handles it.
- Credentials from `Secret`s as env vars; `NetworkPolicy` so only `device-io-worker` can reach device management networks.
- Readiness: the worker is ready once connected to Temporal; liveness via a small health endpoint or process check.

## Rehearse locally (optional)

OpenShift Local (CRC) needs ~4 cores and 10+ GB free RAM. kind/k3d is lighter for practising Deployments + the Worker Controller.

## Done when

- [ ] A merged PR changes `ConfigComplianceWorkflow`; the pipeline replays old histories, deploys a new build, and in-flight remediations finish on the old build while new ones start on the new build.
- [ ] You've written your own `LEARNING.md` summary of the month. Congratulations.

## Solution

Try it yourself first, then compare: [solutions/day30](../../../solutions/day30/SOLUTION.md). Its SOLUTION.md lists the commands to run it and its tests (mock mode by default, so no lab needed).
