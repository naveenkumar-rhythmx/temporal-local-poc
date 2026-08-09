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

## Dashboard / RhythmX AI Tests

| ID | Test | Steps | Expected |
|----|------|-------|----------|
| U1 | Seed pipeline | `./scripts/seed-data.sh` | 6 workflows started, 6 patients reach `status = processed` |
| U2 | Patient list | `GET /patient-services/api/v1/patients` | Every seeded patient with non-zero problem and medication counts |
| U3 | AIREADY collections | `GET /patient-services/api/v1/patient/PAT-20001/air-collections` | Conditions, medications, labs, vitals, appointments, notes all populated |
| U4 | Idempotent re-seed | Run `seed-data.sh` twice | Row counts unchanged (natural-key `ON CONFLICT` upserts) |
| U5 | Dashboard page | `GET /patient-services/dashboard` | HTTP 200, sidebar lists patients, tabs render |
| U6 | Escalation rule | RhythmX panel for `PAT-20001` | High-severity "Diabetes above target", missing-statin, BP-above-target items |
| U7 | Safety rules | RhythmX panel for `PAT-20002` | High-severity hyperkalemia and bleeding-risk items; renal review; polypharmacy |
| U8 | Allergy conflict | RhythmX panel for `PAT-20003` | High-severity allergy conflict on the active amoxicillin course |
| U9 | Duplicate therapy + care gaps | RhythmX panel for `PAT-20006` | Duplicate sulfonylurea, overdue HbA1c, overdue lipid panel |
| U10 | Controlled patient | RhythmX panel for `PAT-20004` | `risk_level = low`, "at goal" recommendation only |
| U11 | Evidence traceability | Any recommendation | `evidence[]` cites the lab/medication/problem that triggered it |
| U12 | Read-only guarantee | Browse every tab | No writes to `patients` or `air_*` (`updated_at` unchanged) |
| U13 | Missing patient | `GET .../patient/PAT-99999/rhythmx` | HTTP 404 |
| U14 | DB outage | `kubectl scale deploy/app-postgres --replicas=0 -n patient-data-services` | `/readyz` reports `degraded`; UI shows an error instead of crashing |
| U15 | Schema upgrade | Run `./scripts/apply-schema.sh` on an existing cluster | Succeeds idempotently; existing rows preserved |

## Automated Coverage

| Script | Coverage |
|--------|----------|
| `scripts/verify.sh` | K1, K2, K4 (partial) |
| `scripts/test-e2e.sh` | F1, F4, F5, D1–D5, U2, U3, U5, plus RhythmX output shape |
| `scripts/seed-data.sh` | U1 |

## Manual Exploratory

1. Open Temporal Web UI: http://localhost:30080
2. Find workflow `patient-PAT-10001-*`
3. Inspect event history: ActivityTaskScheduled → Completed
4. Verify retry entries after R4 failure test

## Exit Criteria

- All F1–F5 pass via `test-e2e.sh`
- At least R1 and R3 demonstrate recovery
- No real PHI used — synthetic data only
