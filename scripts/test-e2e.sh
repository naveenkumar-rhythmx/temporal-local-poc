#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATIENT_API="${PATIENT_API:-http://127.0.0.1:30082}"
TIMEOUT="${E2E_TIMEOUT:-120}"

pass() { echo "$1 : PASS"; }
fail_msg() { echo "$1 : FAIL"; E2E_FAIL=1; }

E2E_FAIL=0

echo "========================================"
echo "Temporal Local E2E Test"
echo "========================================"

PATIENT_JSON='{"patient_id":"PAT-10001","first_name":"John","last_name":"Example","dob":"1985-04-12","encounter_id":"ENC-10001","diagnosis":"EXAMPLE-DIAGNOSIS","source":"local-demo"}'

[[ -f "$ROOT/test-data/patients.json" ]] && pass "Patient input" || fail_msg "Patient input"

if curl -sf "$PATIENT_API/patient-services/health" >/dev/null; then
  pass "Patient API"
else
  fail_msg "Patient API"
fi

if kubectl get deploy temporal-frontend -n temporal >/dev/null 2>&1; then
  pass "Temporal connection"
else
  fail_msg "Temporal connection"
fi

START_RESP=$(curl -sf -X POST "$PATIENT_API/patient-services/api/v1/ingest" \
  -H 'Content-Type: application/json' \
  -d "$PATIENT_JSON" || echo "")

if [[ -n "$START_RESP" ]]; then
  pass "Workflow started"
  WORKFLOW_ID=$(echo "$START_RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin)["workflow_id"])')
else
  fail_msg "Workflow started"
  WORKFLOW_ID=""
fi

if [[ -n "$WORKFLOW_ID" ]]; then
  ELAPSED=0
  RESULT=""
  while [[ $ELAPSED -lt $TIMEOUT ]]; do
    if RESULT=$(curl -sf "$PATIENT_API/patient-services/api/v1/workflows/$WORKFLOW_ID/result" 2>/dev/null); then
      break
    fi
    sleep 3
    ELAPSED=$((ELAPSED + 3))
  done

  if [[ -n "$RESULT" ]]; then
    pass "Worker activity"
    pass "Formatter"
    pass "Workflow completed"
  else
    fail_msg "Worker activity"
    fail_msg "Formatter"
    fail_msg "Workflow completed"
  fi
else
  fail_msg "Worker activity"
  fail_msg "Formatter"
  fail_msg "Workflow completed"
fi

# Query PostgreSQL for formatted output
PG_CHECK=$(kubectl exec -n patient-data-services deploy/app-postgres -- \
  psql -U patient_app -d patient_db -tAc \
  "SELECT count(*) FROM formatted_patient_data WHERE patient_id='PAT-10001';" 2>/dev/null || echo "0")

if [[ "$PG_CHECK" -ge 1 ]]; then
  pass "PostgreSQL write"
else
  fail_msg "PostgreSQL write"
fi

# Validate formatted JSON shape
EXPECTED=$(python3 -c 'import json; print(json.load(open("'"$ROOT"'/test-data/expected-results.json"))["PAT-10001"]["display_name"])')
ACTUAL=$(kubectl exec -n patient-data-services deploy/app-postgres -- \
  psql -U patient_app -d patient_db -tAc \
  "SELECT formatted_json FROM formatted_patient_data WHERE patient_id='PAT-10001' ORDER BY id DESC LIMIT 1;" 2>/dev/null | python3 -c 'import sys,json; print(json.loads(sys.stdin.read().strip()).get("display_name",""))')

if [[ "$ACTUAL" == "$EXPECTED" ]]; then
  pass "Result validation"
else
  fail_msg "Result validation (expected=$EXPECTED actual=$ACTUAL)"
fi

echo ""
if [[ $E2E_FAIL -eq 0 ]]; then
  echo "E2E RESULT: PASS"
else
  echo "E2E RESULT: FAIL"
  exit 1
fi
echo "========================================"
