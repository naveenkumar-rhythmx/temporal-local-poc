#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
kubectl apply -f "$ROOT/namespaces/"
kubectl apply -f "$ROOT/postgres/"
kubectl apply -f "$ROOT/temporal-workflows/k8s/"
kubectl apply -f "$ROOT/temporal-workers/k8s/"
kubectl apply -f "$ROOT/patient-data-services/k8s/"
echo "Manifests applied."
