# End-to-end: 5 patients for today's appointments

Use this on **any personal laptop** (macOS, Linux, Windows, or WSL).  
All data is **synthetic**. Appointment date in the JSON is **2026-08-10**.

| File | Purpose |
|------|---------|
| `test-data/today-5-patients.json` | 5 patients with today's appointments |
| This doc | Exact steps to run the full Raw → Temporal → AIREADY → Dashboard flow |

---

## The 5 patients

| # | Patient | ID | Today's visit |
|---|---------|-----|---------------|
| 1 | Aisha Patel | `PAT-40001` | Diabetes Follow-up |
| 2 | Omar Hassan | `PAT-40002` | Nephrology Consult |
| 3 | Sofia Martinez | `PAT-40003` | Acute Sick Visit |
| 4 | Liam Nguyen | `PAT-40004` | Annual Wellness Visit |
| 5 | Priya Iyer | `PAT-40005` | Medication Review |

---

## Prerequisites (one-time on the laptop)

Install:

- Docker Desktop (running)
- kind
- kubectl
- Helm 3
- curl (or PowerShell)
- Python 3 (for JSON checks; optional on Windows if you use PowerShell only)
- Git

Clone:

```bash
git clone https://github.com/naveenkumar-rhythmx/temporal-local-poc.git
cd temporal-local-poc
```

---

## Step 0 — Start the full Kind stack (first time only)

### macOS / Linux / WSL

```bash
chmod +x scripts/*.sh
./scripts/setup.sh
./scripts/verify.sh
```

### Windows PowerShell

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\verify.ps1
```

Wait until setup finishes. You should see:

- Dashboard: http://127.0.0.1:30082/patient-services/dashboard  
- Temporal UI: http://127.0.0.1:30080  

If the cluster already exists on that laptop, skip to Step 1 (or re-run setup — it is mostly idempotent).

---

## Step 1 — Confirm services are healthy

### bash

```bash
kubectl config use-context kind-temporal-local
curl -s http://127.0.0.1:30082/patient-services/health
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:30080/
kubectl get pods -n patient-data-services
kubectl get pods -n temporal-workers
```

### PowerShell

```powershell
kubectl config use-context kind-temporal-local
Invoke-RestMethod http://127.0.0.1:30082/patient-services/health
kubectl get pods -n patient-data-services
kubectl get pods -n temporal-workers
```

Expect health `{"status":"ok"}` and pods `Running`.

---

## Step 2 — Look at the raw JSON (today's appointments)

Open:

```text
test-data/today-5-patients.json
```

This is the **raw** clinical payload (RXCDM-like): demographics, conditions, meds, allergies, labs, vitals, appointments, notes.  
Every appointment has `"scheduled_at": "2026-08-10"`.

Quick count:

```bash
python3 -c 'import json; print(len(json.load(open("test-data/today-5-patients.json"))), "patients")'
```

---

## Step 3 — Upload raw data (starts Temporal workflows)

This is the real path: **ingest API → workflow starter → Temporal → worker**.

### bash / curl

```bash
curl -sS -X POST http://127.0.0.1:30082/patient-services/api/v1/ingest/batch \
  -H 'Content-Type: application/json' \
  --data-binary @test-data/today-5-patients.json | python3 -m json.tool
```

### PowerShell

```powershell
$body = Get-Content .\test-data\today-5-patients.json -Raw
Invoke-RestMethod -Method POST `
  -Uri "http://127.0.0.1:30082/patient-services/api/v1/ingest/batch" `
  -ContentType "application/json" `
  -Body $body | ConvertTo-Json -Depth 6
```

You should see `"count": 5` and five `workflow_id` values like:

```text
patient-PAT-40001-........
patient-PAT-40002-........
...
```

Copy one `workflow_id` for Step 5 (Temporal UI).

---

## Step 4 — Wait for workers (formatters → AIREADY)

Workers run these activities in order:

1. `validate_patient`
2. `store_raw_patient` → raw tables (`patients`, `patient_events`)
3. `format_patient` → AIREADY-style payload
4. `store_formatted_patient` → `air_*` tables
5. `write_audit_record`

Wait ~10–30 seconds, then check:

### bash

```bash
curl -s http://127.0.0.1:30082/patient-services/api/v1/patients | python3 -m json.tool
```

Look for `PAT-40001` … `PAT-40005` with `"status": "processed"`.

### Or query PostgreSQL

```bash
kubectl exec -n patient-data-services deploy/app-postgres -- \
  psql -U patient_app -d patient_db -c \
  "SELECT patient_id, first_name, last_name, status FROM patients
   WHERE patient_id LIKE 'PAT-400%' ORDER BY patient_id;"
```

AIREADY domain counts:

```bash
kubectl exec -n patient-data-services deploy/app-postgres -- \
  psql -U patient_app -d patient_db -c "
  SELECT 'conditions' t, count(*) FROM air_conditions WHERE patient_id LIKE 'PAT-400%'
  UNION ALL SELECT 'medications', count(*) FROM air_medications WHERE patient_id LIKE 'PAT-400%'
  UNION ALL SELECT 'labs', count(*) FROM air_labs WHERE patient_id LIKE 'PAT-400%'
  UNION ALL SELECT 'vitals', count(*) FROM air_vitals WHERE patient_id LIKE 'PAT-400%'
  UNION ALL SELECT 'appointments', count(*) FROM air_appointments WHERE patient_id LIKE 'PAT-400%'
  UNION ALL SELECT 'notes', count(*) FROM air_clinical_notes WHERE patient_id LIKE 'PAT-400%';
  "
```

Today's appointments:

```bash
kubectl exec -n patient-data-services deploy/app-postgres -- \
  psql -U patient_app -d patient_db -c \
  "SELECT patient_id, appt_type, provider, scheduled_at, status
   FROM air_appointments
   WHERE scheduled_at = '2026-08-10' AND patient_id LIKE 'PAT-400%'
   ORDER BY patient_id;"
```

---

## Step 5 — Watch the flow in Temporal UI

1. Open http://127.0.0.1:30080  
2. Namespace: `default`  
3. Search Workflow ID: `patient-PAT-40001` (or paste full ID from Step 3)  
4. Open a completed workflow  
5. Inspect **Event History**: each activity Scheduled → Started → Completed  

That is the formatter / AIREADY pipeline for one patient.

---

## Step 6 — Open the patient dashboard

1. Open http://127.0.0.1:30082/patient-services/dashboard  
2. Find **Aisha Patel**, **Omar Hassan**, **Sofia Martinez**, **Liam Nguyen**, **Priya Iyer**  
3. Click a patient → tabs:

| Tab | What you see |
|-----|----------------|
| Chart Review | Problems, vitals, today's appointment, Temporal audit |
| Medications | Drugs + allergies |
| Lab Results | Today's labs with H/L flags |
| Notes | Note from today's visit |
| **✦ RhythmX AI** | History summary + recommendations |

### Check RhythmX from the API (optional)

```bash
curl -s http://127.0.0.1:30082/patient-services/api/v1/patient/PAT-40001/rhythmx | python3 -m json.tool
curl -s http://127.0.0.1:30082/patient-services/api/v1/patient/PAT-40003/rhythmx | python3 -m json.tool
```

Expected themes (examples):

- **Aisha** — diabetes above target / missing statin style suggestions  
- **Omar** — renal / potassium / BP safety  
- **Sofia** — penicillin vs amoxicillin conflict; asthma controller gap  
- **Liam** — low risk / at goal  
- **Priya** — bleeding risk (anticoagulant + NSAID); sulfa vs thiazide  

---

## Step 7 — One-command seed (shortcut)

If you prefer not to call curl yourself:

### bash

```bash
./scripts/seed-data.sh test-data/today-5-patients.json
```

### PowerShell

```powershell
.\scripts\seed-data.ps1 -DataFile .\test-data\today-5-patients.json
```

Same pipeline as Step 3–4; waits until patients are `processed`.

---

## End-to-end checklist (print this)

- [ ] Docker Desktop running  
- [ ] `./scripts/setup.sh` (or `.ps1`) completed once  
- [ ] Health OK on `:30082` and Temporal UI on `:30080`  
- [ ] Reviewed `test-data/today-5-patients.json`  
- [ ] Posted batch ingest → 5 workflows started  
- [ ] Patients show `status = processed` in DB / API  
- [ ] `air_*` tables have rows for `PAT-4000x`  
- [ ] Temporal UI shows completed activities for one workflow  
- [ ] Dashboard lists all 5 patients  
- [ ] RhythmX AI tab returns recommendations  

---

## Flow diagram (what you just did)

```text
today-5-patients.json  (RAW / today appointments)
        │
        ▼  POST /patient-services/api/v1/ingest/batch
patient-data-services
        │
        ▼  start workflow
orchestration-core-services
        │
        ▼  task queue: patient-processing
Temporal (UI :30080)
        │
        ▼  validate → store_raw → format → store_formatted → audit
patient-data-worker
        │
        ▼
PostgreSQL patient_db
   raw:     patients, patient_events
   AIREADY: air_conditions, air_medications, air_allergies,
            air_labs, air_vitals, air_appointments, air_clinical_notes
        │
        ▼  read-only
Dashboard (:30082) + RhythmX AI
```

---

## Troubleshooting on the other laptop

| Problem | Fix |
|---------|-----|
| Wrong cluster | `kubectl config use-context kind-temporal-local` |
| Port not open | Confirm Kind cluster exists; re-run setup; use `127.0.0.1` not hostname |
| Workflows hang | `kubectl logs -n temporal-workers deploy/patient-data-worker` |
| Dashboard empty | Re-run Step 3 or `./scripts/seed-data.sh test-data/today-5-patients.json` |
| Reset everything | `./scripts/cleanup.sh` then `./scripts/setup.sh` |

---

## Security note

Synthetic data and local-only passwords only. Do **not** point these scripts at AKS or use real patient data.
