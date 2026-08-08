# PostgreSQL Analysis

## Two PostgreSQL Roles (Critical Distinction)

### 1. Temporal Persistence PostgreSQL (FACT)

**Purpose:** Stores Temporal server internal state — workflow history, task queues, visibility records.

| Cluster | Host | Databases |
|---------|------|-----------|
| AKS (qademo/qa) | Azure Flexible Server (TLS, private endpoint) — hostname redacted | `temporal`, `temporal_visibility` |
| Local POC | `temporal-postgresql.temporal.svc.cluster.local:5432` | `temporal`, `temporal_visibility` |

**Never queried by application business logic directly.**

### 2. Application PostgreSQL (FACT)

**Purpose:** Patient clinical data, L0/L1 processing results, OCS outbox.

| Schema (discovered in gw-rx-patient-data-services) | Tables (representative) |
|-----------------------------------------------------|-------------------------|
| `RXCDM` | PATIENT, ENCOUNTER, CONDITION, MEDICATION, CLINICAL_NOTE, OBSERVATION, ... |
| `HL7_RXCDM` | HL7 fastlane tables |
| `AIREADY` | AIR formatted output tables |
| `REFERENCE_DB` | CUSTOMER_CONFIGS |

**Repositories:**
- `gw-rx-patient-data-services` → read API
- `data-enrichment-services` → formatter writes to AIR
- `gw-rx-star-cdm-bridge` → L0 sync writes to RXCDM
- `orchestration-core-services` → L1 outbox/dispatch tables

## Local Application Schema (`patient_db`)

```sql
patients (
  patient_id, first_name, last_name, date_of_birth, status, created_at
)

patient_events (
  event_id, patient_id, encounter_id, event_type, payload JSONB, source, created_at
)

formatted_patient_data (
  id, patient_id, workflow_id, format_version, formatted_json JSONB, created_at
)

workflow_execution_audit (
  id, workflow_id, run_id, patient_id, status, detail JSONB, created_at
)
```

Deployed as `app-postgres` in `patient-data-services` namespace.

## Connection Strings (Local Only)

```text
Application: postgresql://patient_app:local-only-change-me@app-postgres.patient-data-services.svc.cluster.local:5432/patient_db
Temporal:     postgresql://temporal:temporal@temporal-postgresql.temporal.svc.cluster.local:5432/temporal
```

## AKS vs Local Differences

| Aspect | AKS | Local |
|--------|-----|-------|
| Application PG | Azure Flexible Server, TLS, private endpoint | In-cluster Postgres 16 |
| Temporal PG | Separate Azure server, 512 shards config | Embedded Helm subchart |
| Schema complexity | Full RXCDM + AIR (100+ tables) | 4 demo tables |
| Connection pooling | PgBouncer port 6432 on qademo | Direct connections |

## Verify Local

```bash
kubectl exec -n patient-data-services deploy/app-postgres -- \
  psql -U patient_app -d patient_db -c '\dt'

kubectl exec -n temporal deploy/temporal-postgresql -- \
  psql -U temporal -d temporal -c "SELECT COUNT(*) FROM namespaces;"
```
