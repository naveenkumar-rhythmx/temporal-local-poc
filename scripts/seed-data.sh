#!/usr/bin/env bash
# Seed the dashboard with synthetic patients.
# Every record flows through the real path: ingest API -> workflow starter ->
# Temporal -> worker activities -> PostgreSQL air_* tables. Nothing is inserted directly.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${PATIENT_API_URL:-http://127.0.0.1:30082}"
DATA_FILE="${1:-$ROOT/test-data/clinical-patients.json}"

echo "Seeding $(basename "$DATA_FILE") via $BASE_URL ..."
RESPONSE=$(curl -sS -X POST "$BASE_URL/patient-services/api/v1/ingest/batch" \
  -H 'Content-Type: application/json' \
  --data-binary "@$DATA_FILE")

STARTED=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["count"])' <<<"$RESPONSE")
FAILED=$(python3 -c 'import json,sys; print(len(json.load(sys.stdin)["failed"]))' <<<"$RESPONSE")
echo "Workflows started: $STARTED (failed to start: $FAILED)"

EXPECTED=$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))))' "$DATA_FILE")

echo "Waiting for workflows to finish processing..."
for _ in $(seq 1 40); do
  PROCESSED=$(curl -sS "$BASE_URL/patient-services/api/v1/patients" |
    python3 -c 'import json,sys; print(sum(1 for p in json.load(sys.stdin)["patients"] if p["status"] == "processed"))')
  if [ "$PROCESSED" -ge "$EXPECTED" ]; then
    echo "Processed patients in AIREADY tables: $PROCESSED"
    echo "Dashboard: $BASE_URL/patient-services/dashboard"
    exit 0
  fi
  sleep 3
done

echo "Timed out waiting for all workflows. Check: kubectl logs -n temporal-workers deploy/patient-data-worker"
exit 1
