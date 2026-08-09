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

# Dashboard: ingest a clinical patient, then read the chart and RhythmX panel back
CLINICAL_ID="PAT-20001"
curl -sf -X POST "$PATIENT_API/patient-services/api/v1/ingest/batch" \
  -H 'Content-Type: application/json' \
  --data-binary "@$ROOT/test-data/clinical-patients.json" >/dev/null 2>&1 || true

ELAPSED=0
AIR_COUNT=0
while [[ $ELAPSED -lt $TIMEOUT ]]; do
  AIR_COUNT=$(curl -sf "$PATIENT_API/patient-services/api/v1/patient/$CLINICAL_ID/air-collections" 2>/dev/null |
    python3 -c 'import sys,json; d=json.load(sys.stdin); print(len(d["conditions"]) + len(d["medications"]) + len(d["labs"]))' 2>/dev/null || echo 0)
  [[ "$AIR_COUNT" -gt 0 ]] && break
  sleep 3
  ELAPSED=$((ELAPSED + 3))
done

if [[ "$AIR_COUNT" -gt 0 ]]; then
  pass "AIREADY collections populated"
else
  fail_msg "AIREADY collections populated"
fi

if curl -sf "$PATIENT_API/patient-services/api/v1/patients" |
  python3 -c 'import sys,json; sys.exit(0 if json.load(sys.stdin)["count"] > 0 else 1)'; then
  pass "Dashboard patient list"
else
  fail_msg "Dashboard patient list"
fi

if curl -sf "$PATIENT_API/patient-services/api/v1/patient/$CLINICAL_ID/rhythmx" |
  python3 -c 'import sys,json; d=json.load(sys.stdin); sys.exit(0 if d["history_summary"] and d["recommendations"] else 1)'; then
  pass "RhythmX AI recommendations"
else
  fail_msg "RhythmX AI recommendations"
fi

if [[ "$(curl -s -o /dev/null -w '%{http_code}' "$PATIENT_API/patient-services/dashboard")" == "200" ]]; then
  pass "Dashboard page"
else
  fail_msg "Dashboard page"
fi

echo ""
if [[ $E2E_FAIL -eq 0 ]]; then
  echo "E2E RESULT: PASS"
else
  echo "E2E RESULT: FAIL"
  exit 1
fi
echo "========================================"
