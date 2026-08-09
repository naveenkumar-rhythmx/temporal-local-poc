"""Temporal worker activities for PatientDataWorkflow.

Local analogue of the data-enrichment-services formatter activities: raw patient
data is validated, persisted to the raw layer, formatted per clinical domain, and
written to the AIREADY-style air_* tables that the dashboard reads.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import psycopg
from temporalio import activity

# Coarse drug-class map used by the formatter so downstream decision support can
# reason about therapy classes instead of brand/generic strings.
DRUG_CLASSES: dict[str, str] = {
    "metformin": "biguanide",
    "glipizide": "sulfonylurea",
    "glimepiride": "sulfonylurea",
    "insulin glargine": "insulin",
    "empagliflozin": "sglt2-inhibitor",
    "dapagliflozin": "sglt2-inhibitor",
    "semaglutide": "glp1-agonist",
    "dulaglutide": "glp1-agonist",
    "atorvastatin": "statin",
    "rosuvastatin": "statin",
    "simvastatin": "statin",
    "lisinopril": "ace-inhibitor",
    "enalapril": "ace-inhibitor",
    "losartan": "arb",
    "valsartan": "arb",
    "amlodipine": "calcium-channel-blocker",
    "hydrochlorothiazide": "thiazide-diuretic",
    "chlorthalidone": "thiazide-diuretic",
    "metoprolol": "beta-blocker",
    "carvedilol": "beta-blocker",
    "furosemide": "loop-diuretic",
    "spironolactone": "mra",
    "aspirin": "antiplatelet",
    "clopidogrel": "antiplatelet",
    "apixaban": "anticoagulant",
    "warfarin": "anticoagulant",
    "albuterol": "saba",
    "fluticasone": "inhaled-corticosteroid",
    "levothyroxine": "thyroid-hormone",
    "omeprazole": "ppi",
    "ibuprofen": "nsaid",
    "naproxen": "nsaid",
    "amoxicillin": "penicillin-antibiotic",
    "sertraline": "ssri",
    "gabapentin": "anticonvulsant",
}


def _db_dsn() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://patient_app:local-only-change-me@app-postgres.patient-data-services.svc.cluster.local:5432/patient_db",
    )


def _fail_if_simulated(mode: str) -> None:
    if os.environ.get("SIMULATE_FAILURE") == mode:
        raise RuntimeError(f"Simulated failure: {mode}")


def _drug_class(name: str) -> str | None:
    key = (name or "").strip().lower()
    if key in DRUG_CLASSES:
        return DRUG_CLASSES[key]
    for drug, cls in DRUG_CLASSES.items():
        if drug in key:
            return cls
    return None


def _abnormal_flag(value: Any, low: Any, high: Any) -> str | None:
    """Return H/L/N once a numeric result can be compared to its reference range."""
    if value is None:
        return None
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None
    if high is not None and val > float(high):
        return "H"
    if low is not None and val < float(low):
        return "L"
    return "N"


def _summarize_note(text: str, max_sentences: int = 2) -> str:
    """Extractive note summary.

    Production summarizes clinical notes with an LLM (prompt service + OpenAI).
    This POC keeps it deterministic and offline so results are reproducible.
    """
    clean = re.sub(r"\s+", " ", (text or "").strip())
    if not clean:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    return " ".join(sentences[:max_sentences]).strip()


@activity.defn(name="validate_patient")
async def validate_patient(patient: dict[str, Any]) -> dict[str, Any]:
    _fail_if_simulated("validation")
    required = ["patient_id", "first_name", "last_name", "dob"]
    missing = [k for k in required if not patient.get(k)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    if patient["patient_id"].startswith("INVALID"):
        raise ValueError("Invalid patient_id prefix")
    return {"valid": True, "patient_id": patient["patient_id"]}


@activity.defn(name="store_raw_patient")
async def store_raw_patient(patient: dict[str, Any]) -> dict[str, Any]:
    _fail_if_simulated("database")
    with psycopg.connect(_db_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO patients
                    (patient_id, mrn, first_name, last_name, date_of_birth, gender, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'raw')
                ON CONFLICT (patient_id) DO UPDATE SET
                    mrn = COALESCE(EXCLUDED.mrn, patients.mrn),
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    date_of_birth = EXCLUDED.date_of_birth,
                    gender = COALESCE(EXCLUDED.gender, patients.gender),
                    status = 'raw',
                    updated_at = NOW()
                """,
                (
                    patient["patient_id"],
                    patient.get("mrn"),
                    patient["first_name"],
                    patient["last_name"],
                    patient["dob"],
                    patient.get("gender"),
                ),
            )
            cur.execute(
                """
                INSERT INTO patient_events (patient_id, encounter_id, event_type, payload, source)
                VALUES (%s, %s, 'raw_ingest', %s::jsonb, %s)
                """,
                (
                    patient["patient_id"],
                    patient.get("encounter_id"),
                    json.dumps(patient),
                    patient.get("source", "local-demo"),
                ),
            )
        conn.commit()
    return {"stored": True, "patient_id": patient["patient_id"]}


@activity.defn(name="format_patient")
async def format_patient(patient: dict[str, Any]) -> dict[str, Any]:
    """Build the AIREADY-style per-domain payload from raw patient input."""
    _fail_if_simulated("formatter")
    display_name = f"{patient['first_name']} {patient['last_name']}"

    conditions = [
        {
            "code": c.get("code") or "UNKNOWN",
            "display": c.get("display") or "Unspecified condition",
            "clinical_status": c.get("clinical_status", "active"),
            "onset_date": c.get("onset_date"),
        }
        for c in patient.get("conditions") or []
    ]

    medications = [
        {
            "name": m.get("name") or "Unknown medication",
            "drug_class": m.get("drug_class") or _drug_class(m.get("name", "")),
            "dose": m.get("dose"),
            "route": m.get("route", "oral"),
            "frequency": m.get("frequency"),
            "status": m.get("status", "active"),
            "start_date": m.get("start_date"),
        }
        for m in patient.get("medications") or []
    ]

    allergies = [
        {
            "substance": a.get("substance") or "Unknown",
            "reaction": a.get("reaction"),
            "severity": a.get("severity"),
        }
        for a in patient.get("allergies") or []
    ]

    labs = [
        {
            "code": lab.get("code") or "UNKNOWN",
            "display": lab.get("display") or "Unspecified lab",
            "value": lab.get("value"),
            "unit": lab.get("unit"),
            "ref_low": lab.get("ref_low"),
            "ref_high": lab.get("ref_high"),
            "abnormal_flag": _abnormal_flag(
                lab.get("value"), lab.get("ref_low"), lab.get("ref_high")
            ),
            "collected_at": lab.get("collected_at"),
        }
        for lab in patient.get("labs") or []
    ]

    vitals = [
        {
            "systolic": v.get("systolic"),
            "diastolic": v.get("diastolic"),
            "heart_rate": v.get("heart_rate"),
            "temp_c": v.get("temp_c"),
            "spo2": v.get("spo2"),
            "bmi": v.get("bmi"),
            "recorded_at": v.get("recorded_at"),
        }
        for v in patient.get("vitals") or []
    ]

    appointments = [
        {
            "encounter_id": a.get("encounter_id") or patient.get("encounter_id"),
            "appt_type": a.get("appt_type") or "Office Visit",
            "provider": a.get("provider"),
            "scheduled_at": a.get("scheduled_at"),
            "status": a.get("status", "booked"),
        }
        for a in patient.get("appointments") or []
    ]

    clinical_notes = [
        {
            "encounter_id": n.get("encounter_id") or patient.get("encounter_id"),
            "note_type": n.get("note_type") or "Progress Note",
            "author": n.get("author"),
            "summary": _summarize_note(n.get("text", "")),
            "full_text": n.get("text", ""),
            "note_date": n.get("note_date"),
        }
        for n in patient.get("notes") or []
    ]

    abnormal_labs = [lab["display"] for lab in labs if lab["abnormal_flag"] in ("H", "L")]

    return {
        "patient_id": patient["patient_id"],
        "display_name": display_name,
        "status": "processed",
        "format_version": "v2",
        "summary": {
            "diagnosis": patient.get("diagnosis"),
            "encounter_id": patient.get("encounter_id"),
            "active_problem_count": sum(
                1 for c in conditions if c["clinical_status"] == "active"
            ),
            "active_medication_count": sum(
                1 for m in medications if m["status"] == "active"
            ),
            "abnormal_labs": abnormal_labs,
        },
        "air": {
            "conditions": conditions,
            "medications": medications,
            "allergies": allergies,
            "labs": labs,
            "vitals": vitals,
            "appointments": appointments,
            "clinical_notes": clinical_notes,
        },
    }


@activity.defn(name="store_formatted_patient")
async def store_formatted_patient(payload: dict[str, Any]) -> int:
    """Upsert every AIREADY domain, then record the formatted summary document."""
    _fail_if_simulated("database")
    patient_id = payload["patient_id"]
    formatted = payload["formatted"]
    air = formatted.get("air", {})

    with psycopg.connect(_db_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE patients SET status = 'processed', updated_at = NOW() WHERE patient_id = %s",
                (patient_id,),
            )

            for c in air.get("conditions", []):
                cur.execute(
                    """
                    INSERT INTO air_conditions
                        (patient_id, code, display, clinical_status, onset_date)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (patient_id, code) DO UPDATE SET
                        display = EXCLUDED.display,
                        clinical_status = EXCLUDED.clinical_status,
                        onset_date = EXCLUDED.onset_date,
                        updated_at = NOW()
                    """,
                    (
                        patient_id,
                        c["code"],
                        c["display"],
                        c["clinical_status"],
                        c.get("onset_date"),
                    ),
                )

            for m in air.get("medications", []):
                cur.execute(
                    """
                    INSERT INTO air_medications
                        (patient_id, name, drug_class, dose, route, frequency, status, start_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (patient_id, name) DO UPDATE SET
                        drug_class = EXCLUDED.drug_class,
                        dose = EXCLUDED.dose,
                        route = EXCLUDED.route,
                        frequency = EXCLUDED.frequency,
                        status = EXCLUDED.status,
                        start_date = EXCLUDED.start_date,
                        updated_at = NOW()
                    """,
                    (
                        patient_id,
                        m["name"],
                        m.get("drug_class"),
                        m.get("dose"),
                        m.get("route"),
                        m.get("frequency"),
                        m.get("status", "active"),
                        m.get("start_date"),
                    ),
                )

            for a in air.get("allergies", []):
                cur.execute(
                    """
                    INSERT INTO air_allergies (patient_id, substance, reaction, severity)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (patient_id, substance) DO UPDATE SET
                        reaction = EXCLUDED.reaction,
                        severity = EXCLUDED.severity,
                        updated_at = NOW()
                    """,
                    (patient_id, a["substance"], a.get("reaction"), a.get("severity")),
                )

            for lab in air.get("labs", []):
                if not lab.get("collected_at"):
                    continue
                cur.execute(
                    """
                    INSERT INTO air_labs
                        (patient_id, code, display, value_num, unit, ref_low, ref_high,
                         abnormal_flag, collected_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (patient_id, code, collected_at) DO UPDATE SET
                        display = EXCLUDED.display,
                        value_num = EXCLUDED.value_num,
                        unit = EXCLUDED.unit,
                        ref_low = EXCLUDED.ref_low,
                        ref_high = EXCLUDED.ref_high,
                        abnormal_flag = EXCLUDED.abnormal_flag,
                        updated_at = NOW()
                    """,
                    (
                        patient_id,
                        lab["code"],
                        lab["display"],
                        lab.get("value"),
                        lab.get("unit"),
                        lab.get("ref_low"),
                        lab.get("ref_high"),
                        lab.get("abnormal_flag"),
                        lab["collected_at"],
                    ),
                )

            for v in air.get("vitals", []):
                if not v.get("recorded_at"):
                    continue
                cur.execute(
                    """
                    INSERT INTO air_vitals
                        (patient_id, systolic, diastolic, heart_rate, temp_c, spo2, bmi, recorded_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (patient_id, recorded_at) DO UPDATE SET
                        systolic = EXCLUDED.systolic,
                        diastolic = EXCLUDED.diastolic,
                        heart_rate = EXCLUDED.heart_rate,
                        temp_c = EXCLUDED.temp_c,
                        spo2 = EXCLUDED.spo2,
                        bmi = EXCLUDED.bmi,
                        updated_at = NOW()
                    """,
                    (
                        patient_id,
                        v.get("systolic"),
                        v.get("diastolic"),
                        v.get("heart_rate"),
                        v.get("temp_c"),
                        v.get("spo2"),
                        v.get("bmi"),
                        v["recorded_at"],
                    ),
                )

            for a in air.get("appointments", []):
                cur.execute(
                    """
                    INSERT INTO air_appointments
                        (patient_id, encounter_id, appt_type, provider, scheduled_at, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (patient_id, encounter_id, appt_type) DO UPDATE SET
                        provider = EXCLUDED.provider,
                        scheduled_at = EXCLUDED.scheduled_at,
                        status = EXCLUDED.status,
                        updated_at = NOW()
                    """,
                    (
                        patient_id,
                        a.get("encounter_id"),
                        a["appt_type"],
                        a.get("provider"),
                        a.get("scheduled_at"),
                        a.get("status"),
                    ),
                )

            for n in air.get("clinical_notes", []):
                if not n.get("note_date"):
                    continue
                cur.execute(
                    """
                    INSERT INTO air_clinical_notes
                        (patient_id, encounter_id, note_type, author, summary, full_text, note_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (patient_id, encounter_id, note_type, note_date) DO UPDATE SET
                        author = EXCLUDED.author,
                        summary = EXCLUDED.summary,
                        full_text = EXCLUDED.full_text,
                        updated_at = NOW()
                    """,
                    (
                        patient_id,
                        n.get("encounter_id"),
                        n["note_type"],
                        n.get("author"),
                        n.get("summary"),
                        n.get("full_text"),
                        n["note_date"],
                    ),
                )

            cur.execute(
                """
                INSERT INTO formatted_patient_data
                    (patient_id, workflow_id, format_version, formatted_json)
                VALUES (%s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    patient_id,
                    payload["workflow_id"],
                    formatted.get("format_version", "v1"),
                    json.dumps(formatted),
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return int(row[0])


@activity.defn(name="write_audit_record")
async def write_audit_record(payload: dict[str, Any]) -> int:
    with psycopg.connect(_db_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workflow_execution_audit
                    (workflow_id, run_id, patient_id, status, detail)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    payload["workflow_id"],
                    payload.get("run_id"),
                    payload.get("patient_id"),
                    payload["status"],
                    json.dumps(payload.get("detail", {})),
                ),
            )
            row = cur.fetchone()
        conn.commit()
    return int(row[0])
