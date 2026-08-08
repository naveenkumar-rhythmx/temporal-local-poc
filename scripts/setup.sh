#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CLUSTER_NAME="${CLUSTER_NAME:-temporal-local}"
KUBE_CONTEXT="kind-${CLUSTER_NAME}"

# Ensure we target the local kind cluster, not AKS
if kubectl config get-contexts -o name 2>/dev/null | grep -qx "$KUBE_CONTEXT"; then
  kubectl config use-context "$KUBE_CONTEXT"
else
  echo "Warning: context $KUBE_CONTEXT not found yet; will be created by kind."
fi

if ! kind get clusters 2>/dev/null | grep -qx "$CLUSTER_NAME"; then
  echo "Creating kind cluster $CLUSTER_NAME..."
  kind create cluster --name "$CLUSTER_NAME" --config kind/cluster.yaml
else
  echo "Kind cluster $CLUSTER_NAME already exists (idempotent)."
fi

echo "Creating namespaces..."
kubectl apply -f namespaces/

echo "Building and loading images..."
"$ROOT/scripts/build.sh"

echo "Deploying application PostgreSQL..."
kubectl apply -f postgres/configmap-init.yaml
kubectl apply -f postgres/pvc.yaml
kubectl apply -f postgres/deployment.yaml
kubectl apply -f postgres/service.yaml

echo "Deploying Temporal PostgreSQL (Bitnami)..."
helm repo add bitnami https://charts.bitnami.com/bitnami 2>/dev/null || true
helm repo update bitnami
helm upgrade --install temporal-postgresql bitnami/postgresql \
  -n temporal \
  -f temporal/postgres.yaml \
  --wait --timeout 5m

echo "Creating temporal_visibility database if missing..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=postgresql -n temporal --timeout=300s
PGPOD=$(kubectl get pod -n temporal -l app.kubernetes.io/name=postgresql -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n temporal "$PGPOD" -- bash -c \
  'PGPASSWORD=temporal psql -U temporal -tc "SELECT 1 FROM pg_database WHERE datname = '\''temporal_visibility'\''" | grep -q 1 || PGPASSWORD=temporal psql -U temporal -c "CREATE DATABASE temporal_visibility;"'

echo "Deploying Temporal server (Helm)..."
helm repo add temporal https://go.temporal.io/helm-charts 2>/dev/null || true
helm repo update temporal
kubectl apply -f temporal/namespace.yaml
helm upgrade --install temporal temporal/temporal \
  --version 1.6.0 \
  -n temporal \
  -f temporal/values.yaml \
  --wait --timeout 10m

echo "Waiting for Temporal frontend..."
kubectl wait --for=condition=available deployment/temporal-frontend -n temporal --timeout=300s

echo "Deploying workflow starter, worker, patient-data-services..."
kubectl apply -f temporal-workflows/k8s/deployment.yaml
kubectl apply -f temporal-workers/k8s/deployment.yaml
kubectl apply -f patient-data-services/k8s/deployment.yaml

echo "Waiting for application deployments..."
kubectl wait --for=condition=available deployment/app-postgres -n patient-data-services --timeout=300s
kubectl wait --for=condition=available deployment/orchestration-core-services -n temporal-workflows --timeout=300s
kubectl wait --for=condition=available deployment/patient-data-worker -n temporal-workers --timeout=300s
kubectl wait --for=condition=available deployment/patient-data-services -n patient-data-services --timeout=300s

echo "Running verification..."
"$ROOT/scripts/verify.sh"

echo "Setup complete."
