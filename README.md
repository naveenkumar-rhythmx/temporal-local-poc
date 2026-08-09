# Temporal Local POC

Educational **Kind** Kubernetes prototype of the Temporal architecture used on RhythmX AKS platforms (`qa-platform-rx-aks` / `qademo-platform-aks`).

**Scope:** four namespaces only — `patient-data-services`, `temporal`, `temporal-workers`, `temporal-workflows`.

Works on:

| OS | How to run |
|----|------------|
| **macOS / Linux** | `./scripts/setup.sh` |
| **Windows 10/11** | PowerShell `.\scripts\setup.ps1` (Docker Desktop + Kind) |
| **Windows WSL2** | Bash scripts inside WSL (same as Linux) |

> Synthetic data only. No real PHI. Local-only passwords. Do **not** point these scripts at AKS.

After setup, open the patient dashboard at **http://127.0.0.1:30082/patient-services/dashboard** —
a chart view of every synthetic patient with a **✦ RhythmX AI** tab that summarises the history and
recommends next steps. See [docs/dashboard.md](docs/dashboard.md).

---

## Prerequisites

### All platforms

- [Docker](https://docs.docker.com/get-docker/) (Docker Desktop on Windows/macOS)
- [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Helm 3](https://helm.sh/docs/intro/install/)
- curl or PowerShell (`Invoke-RestMethod`)
- Python 3 (optional; used by macOS/Linux E2E JSON parsing)

### Windows-specific

1. Install **Docker Desktop for Windows** with the **WSL2 backend** enabled.
2. Ensure Docker is running before creating the Kind cluster.
3. Install kind / kubectl / helm (examples):

```powershell
winget install Kubernetes.kubectl
winget install Kubernetes.kind
winget install Helm.Helm
```

4. Run PowerShell scripts from the repo root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\verify.ps1
.\scripts\test-e2e.ps1
```

5. NodePorts `30080–30082` are published via Kind `extraPortMappings` in `kind/cluster.yaml` — use `http://127.0.0.1:30082` from Windows the same as on macOS.

> If Kind cannot pull images, check corporate proxy / VPN settings and that Docker Desktop has enough RAM (recommended **8 GB+**).

---

## Quick start

### macOS / Linux / WSL

```bash
git clone https://github.com/naveenkumar-rhythmx/temporal-local-poc.git
cd temporal-local-poc
chmod +x scripts/*.sh
./scripts/setup.sh
./scripts/verify.sh
./scripts/test-e2e.sh
```

### Windows PowerShell

```powershell
git clone https://github.com/naveenkumar-rhythmx/temporal-local-poc.git
cd temporal-local-poc
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\verify.ps1
.\scripts\test-e2e.ps1
```

---

## Local endpoints

| Service | URL |
|---------|-----|
| **Patient dashboard** | http://127.0.0.1:30082/patient-services/dashboard |
| Temporal Web UI | http://127.0.0.1:30080 |
| Workflow starter (OCS POC) | http://127.0.0.1:30081/health |
| Patient ingest API | http://127.0.0.1:30082/patient-services/health |

---

## Dashboard + RhythmX AI

`./scripts/setup.sh` seeds six synthetic patients automatically. To re-seed at any time:

```bash
./scripts/seed-data.sh          # macOS/Linux/WSL
.\scripts\seed-data.ps1         # Windows
```

Every seeded record travels the real path — ingest API → workflow starter → Temporal →
worker activities → PostgreSQL — so anything visible in the UI is proof the pipeline ran.
The dashboard itself is read-only.

| Tab | Content |
|-----|---------|
| Chart Review | Problem list, vitals, appointments, and the Temporal workflow that produced the record |
| Medications | Active drugs with inferred drug class, plus allergies |
| Lab Results | Latest value per test with reference ranges and H/L flags |
| Notes | Formatter-generated summary over the full note text |
| **✦ RhythmX AI** | History summary, risk level, and ranked recommendations with the evidence behind each one |

The AI panel is a **deterministic rules engine** (`patient-data-services/app/rhythmx.py`) —
offline, no API keys, every suggestion citing the labs/medications/conditions that triggered it.
It covers therapy escalation, drug-safety conflicts, monitoring, and care gaps.
Full details in [docs/dashboard.md](docs/dashboard.md).

> The recommendations are teaching material over fake patients: **not medical advice, not for clinical use.**

---

## Manual ingest example

### bash / curl

```bash
curl -X POST http://127.0.0.1:30082/patient-services/api/v1/ingest \
  -H 'Content-Type: application/json' \
  -d '{"patient_id":"PAT-10002","first_name":"Jane","last_name":"Sample","dob":"1990-07-22","encounter_id":"ENC-10002","diagnosis":"EXAMPLE-CONDITION","source":"local-demo"}'
```

### PowerShell

```powershell
$body = @{
  patient_id   = "PAT-10002"
  first_name   = "Jane"
  last_name    = "Sample"
  dob          = "1990-07-22"
  encounter_id = "ENC-10002"
  diagnosis    = "EXAMPLE-CONDITION"
  source       = "local-demo"
} | ConvertTo-Json

Invoke-RestMethod -Method POST `
  -Uri "http://127.0.0.1:30082/patient-services/api/v1/ingest" `
  -ContentType "application/json" `
  -Body $body
```

---

## Architecture (local)

```text
Synthetic Patient JSON
        ↓
patient-data-services (ingest API)
        ↓
orchestration-core-services (workflow starter)
        ↓
Temporal Frontend → Matching → Task Queue (patient-processing)
        ↓
patient-data-worker
        ↓
validate → store_raw → format → store_formatted → audit
        ↓
app-postgres (patient_db: raw layer + AIREADY air_* tables)
        ↓
patient-data-services (read APIs) → Dashboard + RhythmX AI
```

Read the full clinician journey in [docs/business-flow.md](docs/business-flow.md).

---

## Documentation

| Doc | Content |
|-----|---------|
| [docs/dashboard.md](docs/dashboard.md) | Dashboard + RhythmX AI rules engine |
| [docs/business-flow.md](docs/business-flow.md) | Raw → AIREADY → doctors/nurses |
| [docs/aks-discovery.md](docs/aks-discovery.md) | AKS inventory (sanitized) |
| [docs/architecture.md](docs/architecture.md) | Mermaid diagrams |
| [docs/data-flow.md](docs/data-flow.md) | Step-by-step flow |
| [docs/temporal-analysis.md](docs/temporal-analysis.md) | Temporal components |
| [docs/postgres-analysis.md](docs/postgres-analysis.md) | DB schemas |
| [docs/storage-comparison.md](docs/storage-comparison.md) | Azure vs local |
| [docs/aks-vs-kind.md](docs/aks-vs-kind.md) | Environment comparison |
| [docs/qa-test-plan.md](docs/qa-test-plan.md) | QA / resilience tests |
| [docs/windows-setup.md](docs/windows-setup.md) | Windows Kind notes |

---

## FACT vs ASSUMPTION

| Item | Source |
|------|--------|
| Namespace layout, Temporal 1.31.x on qademo | **FACT** |
| OCS → `temporal-frontend:7233`, namespace `default` | **FACT** |
| DES / L0 workers and ProcessPatientDataWorkflow | **FACT** |
| Separate Temporal PG vs application PG | **FACT** |
| `PatientDataWorkflow` + `patient-processing` queue | **ASSUMPTION** (teaching) |
| patient-data-services as ingest trigger | **ASSUMPTION** (prod uses L0 → OCS) |
| AIREADY holds formatted, clinician-ready data | **FACT** |
| `air_*` table shapes and the RhythmX rule set | **ASSUMPTION** (prod uses an LLM/insight service) |
| Dashboard bundled into patient-data-services | **ASSUMPTION** (prod portal is a separate service) |

---

## Troubleshooting

### Wrong kube context (AKS instead of Kind)

```bash
kubectl config use-context kind-temporal-local
```

```powershell
kubectl config use-context kind-temporal-local
```

`setup` scripts switch to `kind-temporal-local` automatically when that context exists.

### Setup fails on Helm wait

```bash
kubectl get pods -n temporal
kubectl describe pod -n temporal -l app.kubernetes.io/component=frontend
kubectl logs -n temporal -l app.kubernetes.io/component=frontend
```

### Windows: NodePort not reachable

1. Confirm Docker Desktop is running.  
2. `kubectl get svc -A | findstr 3008`  
3. Use `127.0.0.1`, not `localhost` if IPv6 resolves oddly.  
4. Restart Kind: `.\scripts\cleanup.ps1` then `.\scripts\setup.ps1`.

### E2E workflow timeout

```bash
kubectl logs -n temporal-workers deploy/patient-data-worker
kubectl logs -n temporal-workflows deploy/orchestration-core-services
```

### Reset cluster

```bash
./scripts/cleanup.sh    # macOS/Linux
.\scripts\cleanup.ps1   # Windows
```

---

## Security

All credentials in this repo are **local-only placeholders** (`local-only-change-me`, `temporal`). Never reuse them in production. Azure hostnames and production secrets are redacted from the public docs.

---

## License

MIT — see [LICENSE](LICENSE).
