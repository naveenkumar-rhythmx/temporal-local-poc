"""PatientDataWorkflow — simplified local analogue of ProcessPatientDataWorkflow."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from workflows.contracts import PatientInput, WorkflowResult

ACTIVITY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_attempts=3,
)
ACTIVITY_TIMEOUT = timedelta(seconds=30)


@workflow.defn(name="PatientDataWorkflow")
class PatientDataWorkflow:
    @workflow.run
    async def run(self, patient: dict) -> dict:
        workflow_id = workflow.info().workflow_id
        patient_input = PatientInput(**patient)

        await workflow.execute_activity(
            "validate_patient",
            patient_input.to_dict(),
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY,
        )

        await workflow.execute_activity(
            "store_raw_patient",
            patient_input.to_dict(),
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY,
        )

        formatted = await workflow.execute_activity(
            "format_patient",
            patient_input.to_dict(),
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY,
        )

        formatted_id = await workflow.execute_activity(
            "store_formatted_patient",
            {
                "patient_id": patient_input.patient_id,
                "workflow_id": workflow_id,
                "formatted": formatted,
            },
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY,
        )

        domains_written = [
            domain
            for domain, rows in (formatted.get("air") or {}).items()
            if rows
        ]

        audit_id = await workflow.execute_activity(
            "write_audit_record",
            {
                "workflow_id": workflow_id,
                "run_id": workflow.info().run_id,
                "patient_id": patient_input.patient_id,
                "status": "completed",
                "detail": {
                    "formatted_id": formatted_id,
                    "domains_written": domains_written,
                },
            },
            start_to_close_timeout=ACTIVITY_TIMEOUT,
            retry_policy=ACTIVITY_RETRY,
        )

        result = WorkflowResult(
            patient_id=patient_input.patient_id,
            workflow_id=workflow_id,
            status="completed",
            formatted_patient_id=str(formatted_id),
            audit_id=int(audit_id),
            domains_written=domains_written,
        )
        return result.to_dict()
