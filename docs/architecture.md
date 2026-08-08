# Architecture — Discovered AKS vs Local Kind POC

## Discovered AKS Logical Architecture

```mermaid
flowchart TB
    subgraph ingress["Ingress / API Portal"]
        AP[api-portal]
    end

    subgraph pds_ns["patient-data-services"]
        PDS[patient-data-services<br/>FastAPI read API]
    end

    subgraph twf_ns["temporal-workflows"]
        OCS[orchestration-core-services<br/>workflow starter API]
        DISP[OCS dispatcher<br/>L1 outbox → Temporal]
        INS[gw-rx-insight-services]
    end

    subgraph tmp_ns["temporal"]
        FE[temporal-frontend :7233]
        HI[temporal-history]
        MA[temporal-matching]
        TW[temporal-worker]
        WEB[temporal-web :8080]
    end

    subgraph twk_ns["temporal-workers"]
        DES_O[DES orchestrator worker]
        DES_W[DES workflow workers<br/>light/medium/heavy]
        DES_A[DES activity workers<br/>clinical-note, conditions, ...]
        L0B[l0-batch-worker<br/>star-cdm-bridge]
        L0R[l0-rooming-worker]
    end

    subgraph data["External Data Stores"]
        APPPG[(Azure PostgreSQL<br/>RXCDM / L0 / AIR)]
        TMPPG[(Azure PostgreSQL<br/>temporal + temporal_visibility)]
        BLOB[(Azure Blob Storage<br/>clinical note text)]
        AC[(Azure App Configuration)]
    end

    AP --> PDS
    AP --> OCS
    OCS --> FE
    DISP --> FE
    FE --> HI
    FE --> MA
    FE --> TW
    HI --> TMPPG
    MA --> TMPPG
    TW --> TMPPG

    DES_O --> FE
    DES_W --> FE
    DES_A --> FE
    L0B --> FE
    L0R --> FE

    PDS --> APPPG
    PDS --> BLOB
    DES_A --> APPPG
    DES_A --> BLOB
    L0B --> APPPG
    L0B --> BLOB
    OCS --> APPPG
    DES_O --> AC
    L0B --> AC
```

## Local Kind POC Architecture

```mermaid
flowchart TB
    subgraph pds_ns["patient-data-services"]
        PAPI[patient-data-services<br/>ingest API]
        APPPG[(app-postgres<br/>patient_db)]
    end

    subgraph twf_ns["temporal-workflows"]
        WS[orchestration-core-services<br/>workflow starter POC]
    end

    subgraph tmp_ns["temporal"]
        FE[temporal-frontend]
        HI[temporal-history]
        MA[temporal-matching]
        TW[temporal-worker]
        WEB[temporal-web]
        TMPPG[(embedded PostgreSQL<br/>temporal persistence)]
    end

    subgraph twk_ns["temporal-workers"]
        W[patient-data-worker<br/>PatientDataWorkflow]
    end

    PAPI -->|HTTP POST start| WS
    WS -->|gRPC start_workflow| FE
    FE --> HI & MA & TW
    HI & MA & TW --> TMPPG
    W -->|poll patient-processing| FE
    W -->|activities| APPPG
```

## Namespace Mapping

| AKS Namespace | AKS Role | Local POC Equivalent |
|---------------|----------|----------------------|
| patient-data-services | Patient clinical REST API + PG | Simplified ingest API + app-postgres |
| temporal | Temporal server cluster | Helm Temporal + embedded PG |
| temporal-workers | DES + L0 + batch workers | Single `patient-data-worker` |
| temporal-workflows | OCS workflow starter + insight | Workflow starter service (OCS analogue) |

## What Changed Locally (ASSUMPTIONS)

1. **Single workflow** `PatientDataWorkflow` replaces `ProcessPatientDataWorkflow` + 10+ formatter child workflows.
2. **Direct ingest** endpoint replaces multi-hop L0 sync → outbox → dispatcher chain for demo purposes.
3. **No Azure** App Config, Blob, Key Vault, or Managed Identity.
4. **One worker deployment** instead of KEDA-scaled role-specific DES/L0 fleets.

## What Cannot Be Replicated

- Full DES formatter fan-out (appointments, medications, clinical notes, etc.)
- KEDA autoscaling on Temporal task queue depth
- Azure Files Temporal archival (`file://` on RWX PVC)
- Istio sidecars (2/2 containers in AKS pods)
- Production search attributes (`RxPatientId`, `DataPackageId`) — local uses basic workflow IDs only
