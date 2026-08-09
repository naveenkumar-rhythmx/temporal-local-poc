"""OCS-like workflow starter service (temporal-workflows namespace)."""

from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from temporalio.client import Client

from workflows.contracts import TASK_QUEUE, WORKFLOW_NAME

app = FastAPI(title="Temporal Workflow Starter (Local POC)")


class StartWorkflowRequest(BaseModel):
    patient_id: str
    first_name: str
    last_name: str
    dob: str
    mrn: str | None = None
    gender: str | None = None
    encounter_id: str | None = None
    diagnosis: str | None = None
    source: str = "local-demo"
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    medications: list[dict[str, Any]] = Field(default_factory=list)
    allergies: list[dict[str, Any]] = Field(default_factory=list)
    labs: list[dict[str, Any]] = Field(default_factory=list)
    vitals: list[dict[str, Any]] = Field(default_factory=list)
    appointments: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[dict[str, Any]] = Field(default_factory=list)


class StartWorkflowResponse(BaseModel):
    workflow_id: str
    run_id: str
    task_queue: str = Field(default=TASK_QUEUE)


def _temporal_settings() -> tuple[str, str]:
    return (
        os.environ.get(
            "TEMPORAL_HOST", "temporal-frontend.temporal.svc.cluster.local:7233"
        ),
        os.environ.get("TEMPORAL_NAMESPACE", "default"),
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/workflows/start", response_model=StartWorkflowResponse)
async def start_workflow(body: StartWorkflowRequest) -> StartWorkflowResponse:
    temporal_host, namespace = _temporal_settings()

    client = await Client.connect(temporal_host, namespace=namespace)
    workflow_id = f"patient-{body.patient_id}-{uuid.uuid4().hex[:8]}"

    try:
        handle = await client.start_workflow(
            WORKFLOW_NAME,
            body.model_dump(),
            id=workflow_id,
            task_queue=TASK_QUEUE,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return StartWorkflowResponse(
        workflow_id=handle.id,
        run_id=handle.result_run_id or "",
    )


@app.get("/api/v1/workflows/{workflow_id}/result")
async def workflow_result(workflow_id: str) -> dict:
    temporal_host, namespace = _temporal_settings()
    client = await Client.connect(temporal_host, namespace=namespace)
    handle = client.get_workflow_handle(workflow_id)
    try:
        result = await handle.result()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"workflow_id": workflow_id, "result": result}
