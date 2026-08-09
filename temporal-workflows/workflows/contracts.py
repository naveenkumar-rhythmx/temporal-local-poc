"""Shared workflow + activity contracts for the local POC."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TASK_QUEUE = "patient-processing"
WORKFLOW_NAME = "PatientDataWorkflow"

# Clinical domains produced by the formatter activity. Mirrors the per-domain
# formatter fan-out in data-enrichment-services (appointments, medications, ...).
AIR_DOMAINS = (
    "conditions",
    "medications",
    "allergies",
    "labs",
    "vitals",
    "appointments",
    "clinical_notes",
)


@dataclass
class PatientInput:
    patient_id: str
    first_name: str
    last_name: str
    dob: str
    mrn: str | None = None
    gender: str | None = None
    encounter_id: str | None = None
    diagnosis: str | None = None
    source: str = "local-demo"
    conditions: list[dict[str, Any]] = field(default_factory=list)
    medications: list[dict[str, Any]] = field(default_factory=list)
    allergies: list[dict[str, Any]] = field(default_factory=list)
    labs: list[dict[str, Any]] = field(default_factory=list)
    vitals: list[dict[str, Any]] = field(default_factory=list)
    appointments: list[dict[str, Any]] = field(default_factory=list)
    notes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "dob": self.dob,
            "mrn": self.mrn,
            "gender": self.gender,
            "encounter_id": self.encounter_id,
            "diagnosis": self.diagnosis,
            "source": self.source,
            "conditions": self.conditions,
            "medications": self.medications,
            "allergies": self.allergies,
            "labs": self.labs,
            "vitals": self.vitals,
            "appointments": self.appointments,
            "notes": self.notes,
        }


@dataclass
class WorkflowResult:
    patient_id: str
    workflow_id: str
    status: str
    formatted_patient_id: str | None = None
    audit_id: int | None = None
    domains_written: list[str] = field(default_factory=list)
    message: str = "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "workflow_id": self.workflow_id,
            "status": self.status,
            "formatted_patient_id": self.formatted_patient_id,
            "audit_id": self.audit_id,
            "domains_written": self.domains_written,
            "message": self.message,
        }
