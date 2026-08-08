"""Patient data ingress API — local analogue of gw-rx-patient-data-services."""

from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Patient Data Services (Local POC)")


class PatientPayload(BaseModel):
    patient_id: str
    first_name: str
    last_name: str
    dob: str
    encounter_id: str | None = None
    diagnosis: str | None = None
    source: str = Field(default="local-demo")


class IngestResponse(BaseModel):
    patient_id: str
    workflow_id: str
    run_id: str
    status: str = "workflow_started"


@app.get("/patient-services/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/patient-services/api/v1/ingest", response_model=IngestResponse)
async def ingest_patient(body: PatientPayload) -> IngestResponse:
    """Accept synthetic patient JSON and trigger Temporal workflow via workflow-starter."""
    starter_url = os.environ.get(
        "WORKFLOW_STARTER_URL",
        "http://orchestration-core-services.temporal-workflows.svc.cluster.local:8000",
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{starter_url}/api/v1/workflows/start",
                json=body.model_dump(),
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    data = resp.json()
    return IngestResponse(
        patient_id=body.patient_id,
        workflow_id=data["workflow_id"],
        run_id=data.get("run_id", ""),
    )


@app.get("/patient-services/api/v1/workflows/{workflow_id}/result")
async def get_workflow_result(workflow_id: str) -> dict:
    starter_url = os.environ.get(
        "WORKFLOW_STARTER_URL",
        "http://orchestration-core-services.temporal-workflows.svc.cluster.local:8000",
    )
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(f"{starter_url}/api/v1/workflows/{workflow_id}/result")
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()
