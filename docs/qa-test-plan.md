# QA Test Plan — Temporal Local POC

## Functional Tests

| ID | Test | Steps | Expected |
|----|------|-------|----------|
| F1 | Valid patient | `./scripts/test-e2e.sh` | E2E PASS |
| F2 | Invalid patient | POST with `patient_id: INVALID-001` | Workflow fails after retries |
| F3 | Duplicate patient | Ingest PAT-10001 twice | Upsert raw row; 2 formatted rows |
| F4 | Formatter validation | Check `formatted_json.display_name` | Matches expected-results.json |
| F5 | Workflow completion | Poll `/workflows/{id}/result` | status=completed |
| F6 | Workflow retry | Set `SIMULATE_FAILURE=formatter`, ingest, clear env, re-run | First fails; second passes after fix |
| F7 | Workflow timeout | Reduce activity timeout in workflow code | Activity timeout error in Temporal UI |

## Resilience Tests

| ID | Test | Command | Expected |
|----|------|---------|----------|
| R1 | Kill worker pod | `kubectl delete pod -n temporal-workers -l app=patient-data-worker` | Workflow resumes on new pod |
| R2 | Restart worker | `kubectl rollout restart -n temporal-workers deploy/patient-data-worker` | Worker reconnects to queue |
| R3 | Restart PostgreSQL | `kubectl rollout restart -n patient-data-services deploy/app-postgres` | Activities retry until PG ready |
| R4 | Break formatter | `SIMULATE_FAILURE=formatter` on worker | Temporal retries 3x then fails |
| R5 | Restart Temporal frontend | `kubectl rollout restart -n temporal deploy/temporal-frontend` | Clients retry; workflows continue |

## Data Validation

| ID | Check | SQL |
|----|-------|-----|
| D1 | Raw record | `SELECT * FROM patients WHERE patient_id='PAT-10001'` |
| D2 | Event record | `SELECT * FROM patient_events WHERE patient_id='PAT-10001'` |
| D3 | Formatted record | `SELECT formatted_json FROM formatted_patient_data WHERE patient_id='PAT-10001'` |
| D4 | Audit record | `SELECT * FROM workflow_execution_audit WHERE patient_id='PAT-10001'` |
| D5 | Result match | Compare workflow result to expected-results.json |

## Kubernetes Tests

| ID | Test | Command |
|----|------|---------|
| K1 | Pod health | `kubectl get pods -A \| grep -E 'patient-data\|temporal'` |
| K2 | Readiness | All deployments Available=True |
| K3 | Liveness | Kill container; pod restarts |
| K4 | Service connectivity | `curl :30082/patient-services/health` |
| K5 | PVC bound | `kubectl get pvc -n patient-data-services` |
| K6 | Restart behavior | Delete pod; deployment recreates |

## Automated Coverage

| Script | Coverage |
|--------|----------|
| `scripts/verify.sh` | K1, K2, K4 (partial) |
| `scripts/test-e2e.sh` | F1, F4, F5, D1–D5 |

## Manual Exploratory

1. Open Temporal Web UI: http://localhost:30080
2. Find workflow `patient-PAT-10001-*`
3. Inspect event history: ActivityTaskScheduled → Completed
4. Verify retry entries after R4 failure test

## Exit Criteria

- All F1–F5 pass via `test-e2e.sh`
- At least R1 and R3 demonstrate recovery
- No real PHI used — synthetic data only
