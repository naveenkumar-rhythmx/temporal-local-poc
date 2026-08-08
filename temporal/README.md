# Temporal deployment notes (local Kind)

## Components

| Component | Purpose |
|-----------|---------|
| **Frontend** | gRPC API (7233) — clients start/query workflows |
| **History** | Persists workflow event history |
| **Matching** | Routes tasks to worker task queues |
| **Worker (server)** | Internal Temporal system worker |
| **Web UI** | Operator UI (NodePort 30080) |
| **PostgreSQL (embedded)** | Temporal persistence (`temporal`, `temporal_visibility` DBs) |

## Install

Deployed by `./scripts/setup.sh` via:

```bash
helm upgrade --install temporal temporal/temporal \
  -n temporal \
  -f temporal/values.yaml \
  --create-namespace
```

## Verify

```bash
kubectl get pods -n temporal
kubectl get svc -n temporal
kubectl logs -n temporal deploy/temporal-frontend
```

## AKS difference

AKS uses **Azure Database for PostgreSQL** with TLS on port 6432, 512 history shards, dedicated `temporal` node pool, and optional Azure Files archival. Local uses embedded PostgreSQL and 4 shards.
