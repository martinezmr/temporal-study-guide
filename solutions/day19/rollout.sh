#!/usr/bin/env bash
# Practise a Worker Versioning rollout. Run each step by hand and watch the UI between steps.
# Flags can differ slightly between CLI versions: check `temporal worker deployment --help`.
set -euo pipefail
DEPLOY=netops-solutions

echo "1) In terminal A:  BUILD_ID=a1 VERSION=1 uv run python -m solutions.day19.worker"
read -rp "   press enter once it is running... "
temporal worker deployment set-current-version --deployment-name "$DEPLOY" --build-id a1

echo "2) Start 3 audits that will be in flight during the deploy"
for d in bos-rtr-01 bos-acc-01 nyc-rtr-01; do
  temporal workflow start --type DeviceAuditWorkflow --task-queue solutions-day19 \
    --workflow-id "d19-audit-$d-$(date +%s)" --input "\"$d\""
done

echo "3) In terminal B:  BUILD_ID=b2 VERSION=2 uv run python -m solutions.day19.worker"
read -rp "   press enter once it is running... "
temporal worker deployment set-ramping-version --deployment-name "$DEPLOY" --build-id b2 --percentage 25
temporal worker deployment describe --deployment-name "$DEPLOY"

read -rp "4) Promote b2 to current? [enter] "
temporal worker deployment set-current-version --deployment-name "$DEPLOY" --build-id b2
echo "Old runs finish on a1 (pinned). New runs go to b2. Stop worker A once a1 has no running workflows."
