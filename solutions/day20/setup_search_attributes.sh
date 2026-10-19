#!/usr/bin/env bash
# Register the custom search attributes once per namespace (dev server: add --address if needed).
set -euo pipefail
for ns in default compliance; do
  for sa in DeviceName Site ComplianceState; do
    temporal operator search-attribute create --namespace "$ns" --name "$sa" --type Keyword || true
  done
done
temporal operator search-attribute list
