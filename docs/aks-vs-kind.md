# AKS vs Kind Comparison

## Summary

| Environment | Purpose | Temporal Version | Worker Topology |
|-------------|---------|------------------|-----------------|
| qademo-platform-aks | Demo/staging | 1.31.1 | Full DES split + KEDA L0 |
| qa-platform-rx-aks | QA CD | 1.30.3 | Consolidated DES + L0 |
| temporal-local (Kind) | Education/POC | 1.31.1 | Single PatientDataWorkflow worker |

## Component Comparison

### patient-data-services

| | qademo/qa AKS | temporal-local |
|---|---------------|----------------|
| **Implementation** | `gw-rx-patient-data-services` FastAPI, 58.0.0 | Simplified FastAPI ingest proxy |
| **Why it exists** | Clinical data read API for portal/integrations | Demo entry point for synthetic ingest |
| **What changed** | Ingest-only endpoint added; no RXCDM schema | 4-table schema |
| **Cannot replicate** | Full FHIR RXCDM, Azure Blob note text, App Config |

### temporal

| | AKS | Kind |
|---|-----|------|
| **Implementation** | Helm `temporal/temporal` on dedicated node pool | Same chart, no node selectors |
| **Persistence** | Azure PG Flexible Server, TLS :6432 | Embedded PostgreSQL |
| **Replicas** | frontend×4, history×3 | All ×1 |
| **History shards** | 512 | 4 |
| **Archival** | Optional Azure Files `file://` | Disabled |
| **Cannot replicate** | Production shard count, archival, multi-AZ |

### temporal-workflows

| | AKS | Kind |
|---|-----|------|
| **Implementation** | `orchestration-core-services` + dispatcher + insight-services | Workflow starter only |
| **Why** | Start L1/L0 workflows, outbox dispatch, insights | Minimal OCS analogue |
| **Changed** | No outbox, no L1 dispatcher, no insight-services | — |
| **Cannot replicate** | Full OCS API surface, search attributes, auth |

### temporal-workers

| | AKS | Kind |
|---|-----|------|
| **Implementation** | DES (15+ deployments), star-cdm-bridge L0, batch-openai | 1 worker deployment |
| **Workflows** | ProcessPatientDataWorkflow + 10+ formatters + L0 sync | PatientDataWorkflow |
| **Task queues** | 10+ DES queues + L0 queues | `patient-processing` |
| **Scaling** | KEDA on queue depth + CPU HPA | Fixed 1 replica |
| **Cannot replicate** | Full formatter fan-out, LLM batch, KEDA |

## Logical Parity Matrix

| Behavior | AKS | Local POC |
|----------|-----|-----------|
| Durable workflow execution | ✅ | ✅ |
| Activity retries | ✅ | ✅ |
| PostgreSQL application writes | ✅ | ✅ (simplified) |
| Separate Temporal persistence DB | ✅ | ✅ |
| Patient JSON → workflow → formatted output | ✅ (via L0→OCS chain) | ✅ (direct ingest) |
| Azure Blob | ✅ | ❌ |
| Multi-formatter parallel child workflows | ✅ | ❌ |
| Istio mTLS sidecars | ✅ | ❌ |

## Teaching Narrative

Use **qa-platform-rx-aks** as the logical reference (simpler than qademo), but deploy **Temporal 1.31.1** locally to match the newer qademo stack. The local POC teaches the **same Temporal mechanics** (frontend → matching → worker → activities → Postgres) without requiring the full RhythmX release train.
