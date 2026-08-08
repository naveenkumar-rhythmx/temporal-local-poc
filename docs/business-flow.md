# Business Flow — Raw Patient Data to Doctors & Nurses

Educational walkthrough of how clinical data moves from raw upload to AIREADY Postgres and then to hospital clinicians.

> **FACT** = observed from AKS / source repositories  
> **ASSUMPTION** = simplified in this Kind POC

---

## One-sentence summary

Hospital EHR events become raw clinical rows (L0 / RXCDM), Temporal workflows turn them into clinician-ready summaries (L1 / AIREADY), and the portal API serves those summaries to doctors and nurses.

```text
EHR / Files / HL7 / FHIR
        ↓
   RAW storage (Blob + Postgres RXCDM)
        ↓
   L0 sync workers (star-cdm-bridge)
        ↓
   OCS starts Temporal workflow
        ↓
   DES formatters (ProcessPatientDataWorkflow)
        ↓
   AIREADY tables (formatted clinical context)
        ↓
   patient-data-services API
        ↓
   Doctor / Nurse UI (admin portal / EHR integration)
```

---

## Step 1 — Where raw patient data comes from

**FACT (production)**

| Source | What it is | Where it lands first |
|--------|------------|----------------------|
| FHIR pull | Appointments, encounters, conditions, meds | Object storage packages + Postgres `RXCDM` |
| HL7 messages | Labs, notes, ADT events | HL7 path → `HL7_RXCDM` / RXCDM |
| Clinical note files | Full note text | Object storage (Blob) |
| Batch/rooming sync | Scheduled patient sync | L0 Temporal workflows |

**RXCDM** = warehouse of raw clinical facts (“what the EHR said”).

**Local POC (ASSUMPTION)**  
Synthetic JSON posted to the ingest API replaces EHR/Blob packages.

---

## Step 2 — How processing starts

**FACT — production trigger chain**

```text
1. L0 worker syncs patient package
2. Writes/updates Postgres RXCDM tables
3. Marks work for L1 (outbox / data package)
4. orchestration-core-services-dispatcher polls outbox
5. Starts ProcessPatientDataWorkflow via temporal-frontend:7233
```

**Local POC**

```text
POST /patient-services/api/v1/ingest
  → workflow starter (OCS analogue)
  → PatientDataWorkflow on task queue patient-processing
```

---

## Step 3 — Temporal prepares clinician context

**FACT** — `ProcessPatientDataWorkflow` (data-enrichment-services):

1. Validate / bootstrap  
2. Read raw L0 data (and note text from Blob when needed)  
3. Run formatter child workflows (appointments, meds, conditions, labs, notes, …)  
4. Store formatted “AIR details” into **AIREADY**  
5. Lifecycle / audit / cache invalidation  

| Layer | Audience | Content style |
|-------|----------|---------------|
| RXCDM (raw) | Systems | EHR-faithful, coded, noisy |
| AIREADY (formatted) | Doctors / nurses / AI assist | Clean domain summaries |

---

## Step 4 — Final data in Postgres AIREADY

**FACT — application schemas**

| Schema | Role |
|--------|------|
| `RXCDM` | Raw / CDM clinical facts |
| `HL7_RXCDM` | Fastlane HL7 observations |
| `AIREADY` | Formatted clinician context (`AIR_*`) |
| `REFERENCE_DB` | Customer config / filters |

**patient-data-services** exposes AIREADY via air-collections / air-details / cache APIs.

**Local POC tables**

| Local table | Production analogue |
|-------------|---------------------|
| `patients` / `patient_events` | RXCDM raw |
| `formatted_patient_data` | AIREADY `AIR_*` |
| `workflow_execution_audit` | lifecycle / audit |

---

## Step 5 — How doctors and nurses use it

```text
AIREADY (Postgres)
        ↓
patient-data-services (read API)
        ↓
API Portal / Admin Portal / EHR-integrated UI
        ↓
Doctor / Nurse workstation
```

| Clinical need | What formatted data supplies |
|---------------|------------------------------|
| Who is this patient? | Demographics + encounter context |
| What’s going on today? | Appointments, rooming, encounter summary |
| Meds / allergies / problems | Formatted meds, allergies, conditions |
| Labs & vitals | Lab / vitals context |
| Note review | Summarized clinical notes |
| Orders / procedures | Service requests, procedures |

Clinicians do **not** talk to Temporal. They talk to the **portal → patient-data-services → AIREADY**.

---

## Try it locally

```bash
# macOS / Linux / WSL / Git Bash
./scripts/test-e2e.sh
```

```powershell
# Windows PowerShell
.\scripts\test-e2e.ps1
```

Then inspect final rows:

```bash
kubectl exec -n patient-data-services deploy/app-postgres -- \
  psql -U patient_app -d patient_db -c \
  "SELECT patient_id, formatted_json FROM formatted_patient_data ORDER BY id DESC LIMIT 1;"
```
