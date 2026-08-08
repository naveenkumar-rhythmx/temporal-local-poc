# Data Flow — Raw Patient Data to Processed Output

## Discovered Production Flow (FACT)

```text
EHR / HL7 / FHIR ingest (external)
        ↓
L0 sync (gw-rx-star-cdm-bridge workers)
  - RoomingSyncWorkflow / BatchSyncWorkflow / PatientSyncWorkflow
  - Task queues: ROOMING_SYNC_TASK_QUEUE, BATCH_SYNC_TASK_QUEUE
        ↓
PostgreSQL L0 tables (RXCDM schema)
        ↓
orchestration-core-services-dispatcher
  - Polls L1 outbox table
  - L1_DISPATCH_MODE=temporal
  - Starts ProcessPatientDataWorkflow via temporal-frontend:7233
        ↓
Temporal Frontend (temporal namespace)
        ↓
ProcessPatientDataWorkflow (data-enrichment-services)
  - bootstrap_workflow_activity
  - Child formatter workflows per domain (appointments, medications, ...)
  - Activity queues: des-activity-*-queue
  - Workflow queues: des-workflow-light/medium/heavy-queue
        ↓
Formatter activities → PostgreSQL AIR / formatted tables
        ↓
post_lifecycle_activity / audit
        ↓
Workflow result + insight-services read path
```

**patient-data-services role (FACT):** Read API over existing Postgres FHIR/clinical data — it does **not** directly start Temporal workflows in the discovered architecture. Workflows are triggered by OCS/dispatcher and L0 sync pipelines.

## Local POC Flow (ASSUMPTION — simplified teaching model)

```text
Synthetic Patient JSON (test-data/patients.json)
        ↓ HTTP POST /patient-services/api/v1/ingest
patient-data-services (NodePort 30082)
        ↓ HTTP POST /api/v1/workflows/start
orchestration-core-services POC (temporal-workflows, NodePort 30081)
        ↓ gRPC Client.start_workflow
temporal-frontend.temporal.svc:7233
        ↓ task queue: patient-processing
patient-data-worker (temporal-workers)
        ↓
Activities:
  1. validate_patient
  2. store_raw_patient      → patients, patient_events
  3. format_patient         → in-memory transform
  4. store_formatted_patient → formatted_patient_data
  5. write_audit_record     → workflow_execution_audit
        ↓
Workflow result JSON
        ↓
E2E validation (test-e2e.sh)
```

## Arrow-by-Arrow Explanation (Local POC)

| Step | Data | Protocol | K8s Service | Namespace |
|------|------|----------|-------------|-----------|
| Ingest | Patient JSON | HTTP/REST | patient-data-services:80 | patient-data-services |
| Start workflow | Patient dict | HTTP/REST | orchestration-core-services:8000 | temporal-workflows |
| Temporal client | Workflow start request | gRPC | temporal-frontend:7233 | temporal |
| Task dispatch | Workflow tasks | Temporal internal | temporal-matching | temporal |
| Activity execution | Patient rows, formatted JSON | PostgreSQL wire | app-postgres:5432 | patient-data-services |
| Result | WorkflowResult dict | gRPC poll | temporal-frontend:7233 | temporal |

## Failure Behavior (Local)

| Failure | Temporal Behavior |
|---------|-------------------|
| Invalid patient (`INVALID*` prefix) | Activity fails → retry 3x → workflow fails |
| DB unavailable (`SIMULATE_FAILURE=database`) | store_* activities retry with backoff |
| Formatter error (`SIMULATE_FAILURE=formatter`) | format_patient retries then fails |
| Worker pod killed | Tasks remain on queue; new pod resumes after restart |

Set simulation on worker deployment:
```bash
kubectl set env deploy/patient-data-worker -n temporal-workers SIMULATE_FAILURE=formatter
kubectl rollout restart deploy/patient-data-worker -n temporal-workers
# Clear after test:
kubectl set env deploy/patient-data-worker -n temporal-workers SIMULATE_FAILURE-
```
