# Storage Comparison — Azure AKS vs Local Kind

| AKS Azure | Local Kind | Equivalent? | Notes |
|-----------|------------|-------------|-------|
| Azure PostgreSQL (application) | `app-postgres` in patient-data-services | Approximation | Same engine, vastly simplified schema |
| Azure PostgreSQL (Temporal) | Embedded `temporal-postgresql` | Approximation | Same separation of concerns |
| Azure Blob Storage | Not deployed — formatter uses in-memory transform | Partial | FACT: AKS uses Blob for clinical note text (`L0_NOTE_TEXT_BLOB_STORAGE_PREFIX`) |
| Azure Files (Temporal archival RWX) | Not deployed | Not replicated | Optional on AKS via `temporal-archival-pvc` |
| Azure Key Vault | Kubernetes Secrets | Approximation | `postgres-secret`, `application-secret` |
| Azure App Configuration | ConfigMaps + env vars | Approximation | DES/L0 workers load hundreds of keys from App Config in prod |
| Azure Load Balancer | NodePort (30080–30082) | Approximation | kind extraPortMappings |
| Azure DNS | Kubernetes Service DNS | Equivalent | `*.svc.cluster.local` |
| Azure Container Registry | Local Docker + `kind load` | Approximation | Images tagged `temporal-local/*:local` |
| Managed Identity | ServiceAccount (unused in POC) | Partial | AKS pods use `azure.workload.identity/use: "true"` |
| Azure Monitor / Kubesense | kubectl logs/events | Approximation | No Prometheus/Grafana in POC |
| AKS node pools (patient, temporal, workpool) | kind 1 control-plane + 2 workers | Partial | No taints/tolerations locally |

## Azure Blob Usage (FACT — from repositories)

| Service | Blob Usage |
|---------|------------|
| gw-rx-patient-data-services | Clinical note full text (`Binary/` prefix) |
| gw-rx-star-cdm-bridge | `clients/azure_blob/` — L0 data packages |
| gwrx-batch-openai | Batch input/output files |

**Local equivalent if needed:** MinIO or PVC mount. This POC does **not** deploy MinIO — formatter activity operates on JSON in memory/PostgreSQL only.

## Local Persistent Volumes

| PVC | Namespace | Size | Purpose |
|-----|-----------|------|---------|
| app-postgres-pvc | patient-data-services | 2Gi | Application data |
| temporal-postgresql PVC | temporal | 2Gi | Temporal persistence (Helm-created) |

## Recommendation for Extended Local Testing

If testing blob-dependent flows (note upload worker):

```text
Azure Blob Storage  →  MinIO (optional add-on)
                      or  emptyDir / PVC filesystem at /data/blobs
```

Not included in default setup to keep four-namespace scope.
