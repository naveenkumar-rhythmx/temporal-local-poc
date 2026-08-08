# AKS Discovery — qademo-platform-aks & qa-platform-rx-aks

> **Scope:** `patient-data-services`, `temporal`, `temporal-workers`, `temporal-workflows`  
> **Method:** Read-only `kubectl` (no cluster modifications) + repository inspection  
> **Date:** 2026-08-08

## Cluster Contexts

| Cluster | Context | Notes |
|---------|---------|-------|
| qademo-platform-aks | `qademo-platform-aks` | Primary reference; Temporal **1.31.1** |
| qa-platform-rx-aks | `qa-platform-rx-aks` | Target mimic; Temporal **1.30.3** |

## Service Inventory

| Namespace | Workload | Type | Image | Port | Dependency | Purpose |
|-----------|----------|------|-------|------|------------|---------|
| patient-data-services | patient-data-services | Deployment (2/2 qademo) | `qademoplatformacr.azurecr.io/gw-rx-patient-data-services:58.0.0-37c4882` | 80→8000 | Azure PG (RXCDM), Azure Blob, App Config | FastAPI patient clinical data API |
| temporal | temporal-frontend | Deployment (4/4 qademo) | `temporalio/server:1.31.1` | 7233 gRPC | Azure PG (`temporal`, `temporal_visibility`) | Workflow start/query gRPC frontend |
| temporal | temporal-history | Deployment (3/3 qademo) | `temporalio/server:1.31.1` | 7234 | Azure PG | Event history persistence |
| temporal | temporal-matching | Deployment (1/1 qademo) | `temporalio/server:1.31.1` | 7235 | Azure PG | Task queue matching |
| temporal | temporal-worker | Deployment (1/1 qademo) | `temporalio/server:1.31.1` | 7239 | Azure PG | Internal Temporal worker |
| temporal | temporal-web | Deployment (1/1 qademo) | `temporalio/ui:2.51.1` | 8080 | temporal-frontend | Operator UI |
| temporal | temporal-admintools | Deployment (1/1 qademo) | `temporalio/admin-tools:1.31.1` | — | temporal-frontend | CLI/admin |
| temporal-workers | data-enrichment-services-worker-* | Deployments (many) | `data-enrichment-services:58.0.0-0b4d278` | — | Temporal, Azure PG, App Config | DES workers (orchestrator, workflow light/medium/heavy, activity queues) |
| temporal-workers | l0-batch-worker | Deployment (16 qademo) | `star-cdm-bridge:v8-l0-coalesce-8` | — | Temporal, Azure Blob, App Config | L0 batch sync worker |
| temporal-workers | l0-rooming-worker | Deployment (2 qademo) | `star-cdm-bridge:v8-l0-coalesce-8` | — | Temporal | L0 rooming sync worker |
| temporal-workers | l0-note-upload-worker | Deployment (4 qademo) | `star-cdm-bridge:58.0.0-f9960f1` | — | Temporal, Azure Blob | Note upload worker |
| temporal-workers | gwrx-batch-openai-* | Deployment | `gwrx-batch-openai:58.0.0-b59c6f8` | 8080 | Temporal, Azure OpenAI | Batch LLM worker |
| temporal-workers | api-portal | Deployment (2/2 qademo) | `api-portal:58.0.0-f7fee90` | 80 | — | API gateway (ingress) |
| temporal-workflows | orchestration-core-services | Deployment (1/1) | `orchestration-core-services:58.0.0-73f9ec9` | 8000 | Temporal, Azure PG | Start/query workflows (OCS) |
| temporal-workflows | orchestration-core-services-dispatcher | Deployment (1/1) | same image, `--role dispatcher` | — | Temporal, outbox PG | L1 dispatch from outbox |
| temporal-workflows | gw-rx-insight-services | Deployment (2/2 qademo) | `gw-rx-insight-services:v0` | 80 | Azure PG | Insight/read API |

## qa-platform-rx-aks Differences

| Component | qademo | qa-platform-rx |
|-----------|--------|----------------|
| Temporal server | 1.31.1 | 1.30.3 |
| Temporal UI | 2.51.1 | 2.48.1 |
| ACR | qademoplatformacr | qacdrxacr |
| DES worker topology | Split by role (orchestrator, light/medium/heavy, per-activity) | Single `data-enrichment-services-worker` (2 replicas) |
| l0-batch-worker replicas | 16 (KEDA) | 1 |

## Repository Mapping

| AKS Workload | Repository | Path |
|--------------|------------|------|
| patient-data-services | `gw-rx-patient-data-services` | `~/github/gw-rx-patient-data-services` |
| orchestration-core-services | `orchestration-core-services` | `~/github/orchestration-core-services` |
| data-enrichment-services-worker-* | `data-enrichment-services` | `~/github/data-enrichment-services` |
| l0-*-worker | `gw-rx-star-cdm-bridge` | `~/Projects/gw-rx-star-cdm-bridge` |
| temporal (Helm) | `gwrx-deploy` | `services/base-stack/temporal/` |
| gw-rx-insight-services | UNKNOWN - requires repository verification | — |

## ConfigMaps (non-secret keys discovered)

**orchestration-core-services-config:**
- `TEMPORAL_HOST=temporal-frontend.temporal.svc.cluster.local:7233`
- `TEMPORAL_NAMESPACE=default`
- `L1_DISPATCH_MODE=temporal`

**star-cdm-bridge-config:**
- `TEMPORAL_ADDRESS=temporal-frontend.temporal.svc.cluster.local:7233`
- `TEMPORAL_NAMESPACE=default`

**patient-data-services-config:**
- `APP_ENV=qdemo`, `ROOT_PATH_PREFIX=/patient-services`, `AUTH_REQUIRED=false`

## Secrets (key names only — values NOT documented)

| Namespace | Secret | Keys (sample) |
|-----------|--------|---------------|
| patient-data-services | patient-data-services-secret | POSTGRES_PASSWORD, AZURE_STORAGE_CONNECTION_STRING, RX_INTG_API_SECRET_TOKEN, SECRET_KEY |
| temporal | temporal-default-store, temporal-visibility-store | SQL credentials (Helm-managed) |
| temporal-workers | data-enrichment-services-worker-secret | App/db credentials |
| temporal-workflows | orchestration-core-services-secret | DB + app secrets |

## Node Pools (qademo)

| Pool | Workloads |
|------|-----------|
| patientpool | patient-data-services |
| temporal | temporal-* |
| workpool1 | OCS, insight-services, api-portal |
| temporal (workers) | DES + L0 workers |

## UNKNOWN Items

- Exact Azure PG hostnames for application DB (redacted in this public repo)
- Full App Config key catalog per environment
- gw-rx-insight-services source repository location
