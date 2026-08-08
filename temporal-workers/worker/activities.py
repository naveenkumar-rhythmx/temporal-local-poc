"""Temporal worker activities for PatientDataWorkflow."""

from __future__ import annotations

import json
import os
from typing import Any

import psycopg
from temporalio import activity


def _db_dsn() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://patient_app:local-only-change-me@app-postgres.patient-data-services.svc.cluster.local:5432/patient_db",
    )


def _fail_if_simulated(mode: str) -> None:
    if os.environ.get("SIMULATE_FAILURE") == mode:
        raise RuntimeError(f"Simulated failure: {mode}")


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
                INSERT INTO patients (patient_id, first_name, last_name, date_of_birth, status)
                VALUES (%s, %s, %s, %s, 'raw')
                ON CONFLICT (patient_id) DO UPDATE SET
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    date_of_birth = EXCLUDED.date_of_birth,
                    status = 'raw'
                """,
                (
                    patient["patient_id"],
                    patient["first_name"],
                    patient["last_name"],
                    patient["dob"],
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
    _fail_if_simulated("formatter")
    display_name = f"{patient['first_name']} {patient['last_name']}"
    return {
        "patient_id": patient["patient_id"],
        "display_name": display_name,
        "status": "processed",
        "format_version": "v1",
        "summary": {
            "diagnosis": patient.get("diagnosis"),
            "encounter_id": patient.get("encounter_id"),
        },
    }


@activity.defn(name="store_formatted_patient")
async def store_formatted_patient(payload: dict[str, Any]) -> int:
    _fail_if_simulated("database")
    with psycopg.connect(_db_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE patients SET status = 'processed' WHERE patient_id = %s
                """,
                (payload["patient_id"],),
            )
            cur.execute(
                """
                INSERT INTO formatted_patient_data
                    (patient_id, workflow_id, format_version, formatted_json)
                VALUES (%s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    payload["patient_id"],
                    payload["workflow_id"],
                    payload["formatted"].get("format_version", "v1"),
                    json.dumps(payload["formatted"]),
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
