"""Shared workflow + activity contracts for the local POC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TASK_QUEUE = "patient-processing"
WORKFLOW_NAME = "PatientDataWorkflow"


@dataclass
class PatientInput:
    patient_id: str
    first_name: str
    last_name: str
    dob: str
    encounter_id: str | None = None
    diagnosis: str | None = None
    source: str = "local-demo"

    def to_dict(self) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "dob": self.dob,
            "encounter_id": self.encounter_id,
            "diagnosis": self.diagnosis,
            "source": self.source,
        }


@dataclass
class WorkflowResult:
    patient_id: str
    workflow_id: str
    status: str
    formatted_patient_id: str | None = None
    audit_id: int | None = None
    message: str = "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "workflow_id": self.workflow_id,
            "status": self.status,
            "formatted_patient_id": self.formatted_patient_id,
            "audit_id": self.audit_id,
            "message": self.message,
        }
