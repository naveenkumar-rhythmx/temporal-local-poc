#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-temporal-local}"

read -r -p "Delete kind cluster '$CLUSTER_NAME'? [y/N] " ans
if [[ "${ans:-}" =~ ^[Yy]$ ]]; then
  kind delete cluster --name "$CLUSTER_NAME"
  echo "Cluster deleted."
else
  echo "Skipped cluster deletion."
fi
