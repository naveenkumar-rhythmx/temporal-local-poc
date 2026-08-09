"""Queries over the AIREADY-style air_* tables that back the dashboard."""

from __future__ import annotations

from typing import Any

from app.db import query, query_one

# Latest result per lab code, mirroring how a chart shows the most recent value.
LATEST_LABS_SQL = """
SELECT DISTINCT ON (code)
       code, display, value_num, unit, ref_low, ref_high, abnormal_flag, collected_at
FROM air_labs
WHERE patient_id = %s
ORDER BY code, collected_at DESC
"""


def list_patients() -> list[dict[str, Any]]:
    return query(
        """
        SELECT p.patient_id,
               p.mrn,
               p.first_name,
               p.last_name,
               p.date_of_birth,
               p.gender,
               p.status,
               p.updated_at,
               (SELECT COUNT(*) FROM air_conditions c
                 WHERE c.patient_id = p.patient_id AND c.clinical_status = 'active') AS problem_count,
               (SELECT COUNT(*) FROM air_medications m
                 WHERE m.patient_id = p.patient_id AND m.status = 'active') AS medication_count,
               (SELECT COUNT(*) FROM air_labs l
                 WHERE l.patient_id = p.patient_id AND l.abnormal_flag IN ('H', 'L')) AS abnormal_lab_count
        FROM patients p
        ORDER BY p.last_name, p.first_name
        """
    )


def get_patient(patient_id: str) -> dict[str, Any] | None:
    return query_one(
        """
        SELECT patient_id, mrn, first_name, last_name, date_of_birth, gender,
               status, created_at, updated_at
        FROM patients
        WHERE patient_id = %s
        """,
        (patient_id,),
    )


def get_conditions(patient_id: str) -> list[dict[str, Any]]:
    return query(
        """
        SELECT code, display, clinical_status, onset_date
        FROM air_conditions
        WHERE patient_id = %s
        ORDER BY clinical_status, display
        """,
        (patient_id,),
    )


def get_medications(patient_id: str) -> list[dict[str, Any]]:
    return query(
        """
        SELECT name, drug_class, dose, route, frequency, status, start_date
        FROM air_medications
        WHERE patient_id = %s
        ORDER BY status, name
        """,
        (patient_id,),
    )


def get_allergies(patient_id: str) -> list[dict[str, Any]]:
    return query(
        """
        SELECT substance, reaction, severity
        FROM air_allergies
        WHERE patient_id = %s
        ORDER BY substance
        """,
        (patient_id,),
    )


def get_labs(patient_id: str) -> list[dict[str, Any]]:
    return query(
        """
        SELECT code, display, value_num, unit, ref_low, ref_high, abnormal_flag, collected_at
        FROM air_labs
        WHERE patient_id = %s
        ORDER BY collected_at DESC, display
        """,
        (patient_id,),
    )


def get_latest_labs(patient_id: str) -> list[dict[str, Any]]:
    return query(LATEST_LABS_SQL, (patient_id,))


def get_vitals(patient_id: str) -> list[dict[str, Any]]:
    return query(
        """
        SELECT systolic, diastolic, heart_rate, temp_c, spo2, bmi, recorded_at
        FROM air_vitals
        WHERE patient_id = %s
        ORDER BY recorded_at DESC
        """,
        (patient_id,),
    )


def get_appointments(patient_id: str) -> list[dict[str, Any]]:
    return query(
        """
        SELECT encounter_id, appt_type, provider, scheduled_at, status
        FROM air_appointments
        WHERE patient_id = %s
        ORDER BY scheduled_at DESC NULLS LAST
        """,
        (patient_id,),
    )


def get_notes(patient_id: str) -> list[dict[str, Any]]:
    return query(
        """
        SELECT encounter_id, note_type, author, summary, full_text, note_date
        FROM air_clinical_notes
        WHERE patient_id = %s
        ORDER BY note_date DESC
        """,
        (patient_id,),
    )


def get_workflow_audit(patient_id: str) -> list[dict[str, Any]]:
    return query(
        """
        SELECT workflow_id, run_id, status, detail, created_at
        FROM workflow_execution_audit
        WHERE patient_id = %s
        ORDER BY created_at DESC
        LIMIT 10
        """,
        (patient_id,),
    )


def get_air_collections(patient_id: str) -> dict[str, Any]:
    """Everything the chart needs for one patient, in one payload."""
    return {
        "patient": get_patient(patient_id),
        "conditions": get_conditions(patient_id),
        "medications": get_medications(patient_id),
        "allergies": get_allergies(patient_id),
        "labs": get_labs(patient_id),
        "latest_labs": get_latest_labs(patient_id),
        "vitals": get_vitals(patient_id),
        "appointments": get_appointments(patient_id),
        "notes": get_notes(patient_id),
        "workflow_audit": get_workflow_audit(patient_id),
    }
