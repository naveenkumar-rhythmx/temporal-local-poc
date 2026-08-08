# Temporal Analysis

## Discovered AKS Deployment

| Property | qademo-platform-aks | qa-platform-rx-aks |
|----------|---------------------|---------------------|
| Helm chart | `temporal-1.5.0` | UNKNOWN - same chart assumed |
| Server image | `temporalio/server:1.31.1` | `temporalio/server:1.30.3` |
| UI image | `temporalio/ui:2.51.1` | `temporalio/ui:2.48.1` |
| Admin tools | `temporalio/admin-tools:1.31.1` | `temporalio/admin-tools:1.30.3` |
| Frontend replicas | 4 (HPA max 4) | 2 |
| History replicas | 3 | 1 |
| Matching replicas | 1 (HPA max 3) | 1 |
| Frontend port | 7233 gRPC | 7233 gRPC |
| Web port | 8080 | 8080 |
| Temporal namespace | `default` | `default` (assumed) |
| History shards | 512 | 512 (from values-r20.yaml) |

## Persistence (FACT — from Helm values)

```yaml
# Azure PostgreSQL — two logical databases (host redacted for public docs):
default store:     databaseName: temporal
visibility store:  databaseName: temporal_visibility
driver: postgres12
connectAddr: <azure-postgres-host>:6432   # TLS enabled in AKS
manageSchema: false  # schema managed externally
```

Secrets in cluster: `temporal-default-store`, `temporal-visibility-store`

## Component Responsibilities

| Component | Role |
|-----------|------|
| **Frontend** | Public gRPC API for workers and clients; workflow start/signal/query |
| **History** | Append-only workflow event history; drives replay |
| **Matching** | Matches tasks to pollers on task queues |
| **Worker (server)** | System workflows (archival, replication helpers) |
| **Web** | UI for operators |
| **Admintools** | `temporal` CLI in cluster |

## Discovered Task Queues (Production)

### star-cdm-bridge (L0)
- `ROOMING_SYNC_TASK_QUEUE` (default env `L0_ROOMING_SYNC_TASK_QUEUE`)
- `BATCH_SYNC_TASK_QUEUE` (default env `L0_BATCH_SYNC_TASK_QUEUE`)

### data-enrichment-services (L1)
- `des-workflow-orchestrator-queue`
- `des-workflow-light-queue`, `des-workflow-medium-queue`, `des-workflow-heavy-queue`
- `des-activity-default-queue`
- `des-activity-clinical-note-queue`
- (+ conditions, medications, lab-context, lifestyle-factors queues)

### orchestration-core-services
- Derives task queue from `workflow_name` via App Config mapping
- L1 workflow: `ProcessPatientDataWorkflow`
- L0 queues: `L0_PRIORITY_TASK_QUEUE`, `L0_STANDARD_TASK_QUEUE`

## Local POC

| Property | Value |
|----------|-------|
| Server version | 1.31.1 (matches qademo) |
| Persistence | Embedded Bitnami PostgreSQL in `temporal` namespace |
| History shards | 4 (reduced for local) |
| Task queue | `patient-processing` |
| Workflow | `PatientDataWorkflow` |

## Retry Policy (Local POC — matches prompt spec)

```python
initial_interval = 2 seconds
backoff_coefficient = 2.0
maximum_attempts = 3
activity_timeout = 30 seconds
```

## Observability (Local)

```bash
# Pod health
kubectl get pods -n temporal

# Frontend logs
kubectl logs -n temporal deploy/temporal-frontend -f

# Worker task processing
kubectl logs -n temporal-workers deploy/patient-data-worker -f

# Cluster events
kubectl get events -n temporal --sort-by='.lastTimestamp'

# Temporal Web UI
open http://localhost:30080
```

Production uses Grafana dashboards in `rx-kubesense` repo — not replicated locally.
