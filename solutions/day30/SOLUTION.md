# Day 30 — Solution

| File | Role |
| --- | --- |
| `../day21/Containerfile` | One image for every role (random-UID friendly for OpenShift) |
| `../day29/workers.py` | Entrypoint: `WORKER_ROLE` / first arg = `orchestration`, `device-io` or `compliance` |
| `k8s/` | Kustomize: ConfigMap, example Secret, 3 Deployments, NetworkPolicies |
| `replay_histories.py` | The CI gate: replays `tests/histories/*.json` against the current commit |
| `ci-cd.yml` | GitHub Actions: test → replay → build/push → deploy (deploy steps are TODO placeholders) |

> **Note:** `../day21/Containerfile` defaults to the Day 21 workers. The Deployments override `command:` to run `solutions.day29.workers`.

```bash
uv run python -m solutions.day30.replay_histories tests/histories
uv run pytest solutions/tests/test_day30.py
podman build -f solutions/day21/Containerfile -t netops-worker --build-arg BUILD_ID=$(git rev-parse --short HEAD) .
oc apply -k solutions/day30/k8s      # after filling in the TODOs
```

## The release loop

1. A PR changes `ConfigComplianceWorkflow`.
2. **test**: unit and workflow tests in mock mode.
3. **replay**: every exported history must replay against the new code. A non-deterministic change fails here, before it can touch a running remediation. Fix it with a patch (Day 19) or a new workflow type.
4. **build**: image tagged with the git SHA, which is also the worker's `BUILD_ID`.
5. **deploy**: the new Deployment starts alongside the old one. Ramp, then set it as current. Pinned remediations finish on the old build; the AUTO_UPGRADE orchestrator moves to the new one. Delete the old Deployment once it has no running pinned workflows. The **Temporal Worker Controller** automates exactly this loop on Kubernetes.

## OpenShift checklist

- [ ] Image runs as an arbitrary UID (`chgrp 0` / `chmod g=u` in the Containerfile, `runAsNonRoot`).
- [ ] `terminationGracePeriodSeconds` > the worker's `graceful_shutdown_timeout`.
- [ ] Credentials only via Secrets; `grep` an exported history for them.
- [ ] NetworkPolicy: only device-io/compliance pods reach the device management network.
- [ ] Temporal: self-hosted (Helm + PostgreSQL, UI behind a Route, mTLS) or Temporal Cloud (workers only in OCP).
- [ ] Search attributes registered in each namespace (Day 20) and the Nexus endpoint created (`workers setup`).
