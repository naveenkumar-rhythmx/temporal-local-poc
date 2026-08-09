"""Patient data services — ingest API, chart read APIs, and the local dashboard.

Local analogue of gw-rx-patient-data-services: it serves formatted (AIREADY-style)
clinical data to the UI. In the real platform the portal is a separate service
behind api-portal; here the dashboard is bundled to stay inside the four
namespaces of this prototype.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import repository, rhythmx
from app.db import ping

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Patient Data Services (Local POC)")
app.mount("/patient-services/static", StaticFiles(directory=STATIC_DIR), name="static")


class PatientPayload(BaseModel):
    patient_id: str
    first_name: str
    last_name: str
    dob: str
    mrn: str | None = None
    gender: str | None = None
    encounter_id: str | None = None
    diagnosis: str | None = None
    source: str = Field(default="local-demo")
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    medications: list[dict[str, Any]] = Field(default_factory=list)
    allergies: list[dict[str, Any]] = Field(default_factory=list)
    labs: list[dict[str, Any]] = Field(default_factory=list)
    vitals: list[dict[str, Any]] = Field(default_factory=list)
    appointments: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[dict[str, Any]] = Field(default_factory=list)


class IngestResponse(BaseModel):
    patient_id: str
    workflow_id: str
    run_id: str
    status: str = "workflow_started"


def _starter_url() -> str:
    return os.environ.get(
        "WORKFLOW_STARTER_URL",
        "http://orchestration-core-services.temporal-workflows.svc.cluster.local:8000",
    )


async def _start_workflow(client: httpx.AsyncClient, body: PatientPayload) -> IngestResponse:
    resp = await client.post(
        f"{_starter_url()}/api/v1/workflows/start",
        json=body.model_dump(),
    )
    resp.raise_for_status()
    data = resp.json()
    return IngestResponse(
        patient_id=body.patient_id,
        workflow_id=data["workflow_id"],
        run_id=data.get("run_id", ""),
    )


# --------------------------------------------------------------- operations
@app.get("/patient-services/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/patient-services/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ok" if ping() else "degraded", "database": str(ping())}


@app.get("/")
async def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/patient-services/dashboard")


@app.get("/patient-services/dashboard", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# ------------------------------------------------------------------- ingest
@app.post("/patient-services/api/v1/ingest", response_model=IngestResponse)
async def ingest_patient(body: PatientPayload) -> IngestResponse:
    """Accept synthetic patient JSON and trigger the Temporal workflow."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            return await _start_workflow(client, body)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/patient-services/api/v1/ingest/batch")
async def ingest_batch(body: list[PatientPayload]) -> dict[str, Any]:
    """Seed many patients through the same Temporal pipeline."""
    started: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        for patient in body:
            try:
                result = await _start_workflow(client, patient)
                started.append(result.model_dump())
            except httpx.HTTPError as exc:
                failed.append({"patient_id": patient.patient_id, "error": str(exc)})
    return {"started": started, "failed": failed, "count": len(started)}


@app.get("/patient-services/api/v1/workflows/{workflow_id}/result")
async def get_workflow_result(workflow_id: str) -> dict:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(f"{_starter_url()}/api/v1/workflows/{workflow_id}/result")
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


# -------------------------------------------------------------- chart reads
@app.get("/patient-services/api/v1/patients")
async def list_patients() -> dict[str, Any]:
    patients = repository.list_patients()
    return {"count": len(patients), "patients": patients}


@app.get("/patient-services/api/v1/patient/{patient_id}")
async def get_patient(patient_id: str) -> dict[str, Any]:
    patient = repository.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")
    return patient


@app.get("/patient-services/api/v1/patient/{patient_id}/air-collections")
async def air_collections(patient_id: str) -> dict[str, Any]:
    """All formatted (AIREADY-style) collections for one patient."""
    if repository.get_patient(patient_id) is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")
    return repository.get_air_collections(patient_id)


@app.get("/patient-services/api/v1/patient/{patient_id}/rhythmx")
async def rhythmx_panel(patient_id: str) -> dict[str, Any]:
    """RhythmX AI panel: history summary + rules-based recommendations."""
    result = rhythmx.analyze(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")
    return result
