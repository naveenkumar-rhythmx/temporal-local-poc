#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

pass() { echo "$1 : PASS"; }
fail() { echo "$1 : FAIL"; exit 1; }

echo "========================================"
echo "Temporal Local Verification"
echo "========================================"

for ns in patient-data-services temporal temporal-workers temporal-workflows; do
  kubectl get ns "$ns" >/dev/null 2>&1 && pass "Namespace $ns" || fail "Namespace $ns"
done

kubectl get deploy app-postgres -n patient-data-services >/dev/null 2>&1 && pass "Application PostgreSQL" || fail "Application PostgreSQL"
kubectl get deploy temporal-frontend -n temporal >/dev/null 2>&1 && pass "Temporal frontend" || fail "Temporal frontend"
kubectl get deploy patient-data-worker -n temporal-workers >/dev/null 2>&1 && pass "Temporal worker" || fail "Temporal worker"
kubectl get deploy orchestration-core-services -n temporal-workflows >/dev/null 2>&1 && pass "Workflow starter" || fail "Workflow starter"
kubectl get deploy patient-data-services -n patient-data-services >/dev/null 2>&1 && pass "Patient API" || fail "Patient API"

echo "========================================"
echo "VERIFY RESULT: PASS"
echo "========================================"
