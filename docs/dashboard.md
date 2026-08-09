# Patient Dashboard + RhythmX AI Panel

A minimal clinician-facing chart view served by `patient-data-services`. It reads
only the **formatted (AIREADY-style) `air_*` tables** — the same data a real
portal would read — so the dashboard proves the Temporal pipeline actually
produced usable clinical output.

- **URL:** http://127.0.0.1:30082/patient-services/dashboard
- **Data:** synthetic patients only, seeded through Temporal (never inserted directly)
- **AI panel:** deterministic rules engine, offline, no API keys

> Educational prototype. Every recommendation is rules-based output over fake
> patients — **not medical advice, not for clinical use.**

---

## 1. How data reaches the dashboard

```text
test-data/clinical-patients.json
        │  POST /patient-services/api/v1/ingest/batch
        ▼
patient-data-services  (ingest API, namespace: patient-data-services)
        │  POST /api/v1/workflows/start
        ▼
orchestration-core-services  (workflow starter, namespace: temporal-workflows)
        │  gRPC :7233
        ▼
Temporal frontend → matching → task queue "patient-processing"  (namespace: temporal)
        ▼
patient-data-worker  (namespace: temporal-workers)
        │  validate_patient
        │  store_raw_patient        → patients, patient_events        (raw layer)
        │  format_patient           → per-domain AIREADY payload
        │  store_formatted_patient  → air_* tables + formatted_patient_data
        │  write_audit_record       → workflow_execution_audit
        ▼
app-postgres / patient_db
        ▲
        │  read-only SQL
patient-data-services  →  dashboard + RhythmX AI panel
```

The dashboard performs **no writes**. Nothing appears in the UI unless a Temporal
workflow completed successfully, which makes the UI a functional test of the pipeline.

---

## 2. Tabs

| Tab | Reads from | Shows |
|-----|-----------|-------|
| Chart Review | `air_conditions`, `air_vitals`, `air_appointments`, `workflow_execution_audit` | Problem list, vitals history, upcoming visits, the Temporal workflow that produced the record |
| Medications | `air_medications`, `air_allergies` | Active/inactive drugs with inferred drug class, allergy list |
| Lab Results | `air_labs` | Latest value per test with reference ranges and H/L/N flags, plus full history |
| Notes | `air_clinical_notes` | Formatter-generated summary with the full note text collapsed underneath |
| **✦ RhythmX AI** | `/api/v1/patient/{id}/rhythmx` | History summary, risk level, ranked recommendations with evidence |

---

## 3. RhythmX AI engine

`patient-data-services/app/rhythmx.py`. Deterministic and auditable: each
recommendation carries the exact data points that triggered it.

**Inputs:** active problem list, active medications (with drug class), allergies,
latest result per lab code, most recent vitals, patient age.

**Rule families:**

| Family | Examples |
|--------|----------|
| Therapy escalation | HbA1c ≥ 8% on limited therapy; LDL ≥ 100 despite a statin; no statin with diabetes/ASCVD over 40; BP ≥ 140/90 on fewer than two agents |
| Safety | Allergy-versus-active-drug conflicts; anticoagulant combined with NSAID/antiplatelet; duplicate therapy within one drug class; reduced eGFR with renally-cleared drugs; high potassium on ACEi/ARB/MRA |
| Monitoring | Polypharmacy (8+ active drugs); TSH above range on levothyroxine |
| Care gaps | HbA1c older than ~120 days in diabetes; no lipid panel within a year; no vitals recorded |

**Output shape:**

```json
{
  "risk_level": "high",
  "counts": { "high": 2, "moderate": 2, "low": 0 },
  "history_summary": "James Carter is a 72-year-old male with an active problem list of ...",
  "recommendations": [
    {
      "id": "hyperkalemia-watch",
      "category": "Safety",
      "severity": "high",
      "title": "Elevated potassium with RAAS-acting therapy",
      "detail": "Potassium is 5.6 mmol/L while on ace-inhibitor. Repeat and review dosing.",
      "suggested_options": ["Repeat potassium", "Review ACEi/ARB/MRA dose"],
      "evidence": ["Potassium: 5.6 mmol/L (2026-07-30)"]
    }
  ],
  "disclaimer": "Educational prototype running on synthetic data. ..."
}
```

`risk_level` is `high` if any high-severity item fired, otherwise `moderate`, otherwise `low`.

**FACT vs ASSUMPTION:** production derives insights with an LLM/prompt service
reading AIREADY collections — **FACT**. This specific rule set, its thresholds,
and the drug-class table are teaching material for the POC — **ASSUMPTION**.

---

## 4. Seeded patients

Six synthetic patients in `test-data/clinical-patients.json`, each chosen to
exercise a different branch of the engine.

| Patient | Clinical picture | Expected panel |
|---------|------------------|----------------|
| Maria Lopez (`PAT-20001`) | T2DM + hypertension + obesity, metformin only, A1c 8.4%, BP 152/94 | high — therapy escalation, missing statin, BP above target |
| James Carter (`PAT-20002`) | CAD, CKD stage 3, AF; 8 drugs including ibuprofen with apixaban + aspirin; eGFR 38, K 5.6 | high — hyperkalemia, bleeding risk, renal review, polypharmacy |
| Priya Nair (`PAT-20003`) | Asthma + hypothyroidism, penicillin allergy with an **active amoxicillin** course, TSH 6.8 | high — allergy conflict, reliever without controller, thyroid dose |
| Daniel Okafor (`PAT-20004`) | Well-controlled T2DM, A1c 6.5%, on statin and ACEi | low — at goal, continue regimen |
| Emily Chen (`PAT-20005`) | HTN + AF + osteoarthritis, sulfa allergy on hydrochlorothiazide, naproxen with apixaban | high — allergy conflict, bleeding risk, BP above target |
| Robert Vega (`PAT-20006`) | T2DM with stale labs, two sulfonylureas, BP 162/98 | high — escalation, duplicate class, overdue A1c and lipids |

---

## 5. API reference

All paths are relative to `http://127.0.0.1:30082`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/patient-services/dashboard` | The dashboard page |
| GET | `/patient-services/api/v1/patients` | Patient list with problem/medication/abnormal counts |
| GET | `/patient-services/api/v1/patient/{id}` | Demographics banner |
| GET | `/patient-services/api/v1/patient/{id}/air-collections` | All AIREADY domains for one patient |
| GET | `/patient-services/api/v1/patient/{id}/rhythmx` | RhythmX AI panel |
| POST | `/patient-services/api/v1/ingest` | Start one workflow |
| POST | `/patient-services/api/v1/ingest/batch` | Start workflows for an array of patients |
| GET | `/patient-services/readyz` | Database connectivity check |

```bash
# Seed the dashboard (idempotent — safe to re-run)
./scripts/seed-data.sh

# Inspect one patient's AI panel
curl -s http://127.0.0.1:30082/patient-services/api/v1/patient/PAT-20002/rhythmx | python3 -m json.tool
```

---

## 6. Schema

The dashboard depends on the AIREADY-style tables created by `postgres/init.sql`:

`air_conditions`, `air_medications`, `air_allergies`, `air_labs`, `air_vitals`,
`air_appointments`, `air_clinical_notes`.

Each has a natural-key `UNIQUE` constraint so the worker can `ON CONFLICT ... DO UPDATE`.
Re-ingesting the same patient updates the chart instead of duplicating rows, which is
what makes Temporal's at-least-once activity retries safe here.

`scripts/apply-schema.sh` re-applies the schema to a running cluster. It is idempotent
(`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`), so it also upgrades a
PostgreSQL volume that was initialised by an older version of this repo — the
container's `docker-entrypoint-initdb.d` scripts only run on first boot.

---

## 7. Troubleshooting

**Sidebar says "No patients found":** the seed has not run.

```bash
./scripts/seed-data.sh
```

**Patients listed but tabs are empty:** the worker wrote the raw layer but not the
AIREADY layer, usually an old worker image. Rebuild, restart, then re-seed.

```bash
./scripts/build.sh
kubectl rollout restart deploy/patient-data-worker -n temporal-workers
kubectl rollout status  deploy/patient-data-worker -n temporal-workers
./scripts/seed-data.sh
```

**RhythmX AI panel shows an error:** check the database connection.

```bash
curl -s http://127.0.0.1:30082/patient-services/readyz
kubectl logs -n patient-data-services deploy/patient-data-services
```

**Verify what actually landed in PostgreSQL:**

```bash
kubectl exec -n patient-data-services deploy/app-postgres -- \
  psql -U patient_app -d patient_db -c \
  "SELECT patient_id, status FROM patients ORDER BY patient_id;"
```
