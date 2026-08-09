#!/usr/bin/env bash
# Apply/refresh the application schema on the running app-postgres.
# Idempotent: init.sql uses CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS,
# so this also upgrades clusters whose PVC was initialised by an older schema.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NS=patient-data-services

echo "Publishing schema ConfigMap from postgres/init.sql..."
kubectl create configmap app-postgres-init \
  --from-file=init.sql="$ROOT/postgres/init.sql" \
  -n "$NS" --dry-run=client -o yaml | kubectl apply -f -

if kubectl get deploy app-postgres -n "$NS" >/dev/null 2>&1; then
  echo "Waiting for app-postgres to be ready..."
  kubectl wait --for=condition=available deployment/app-postgres -n "$NS" --timeout=300s

  echo "Applying schema to patient_db..."
  kubectl exec -i -n "$NS" deploy/app-postgres -- \
    psql -U patient_app -d patient_db -v ON_ERROR_STOP=1 -q -f - < "$ROOT/postgres/init.sql"
  echo "Schema applied."
fi
