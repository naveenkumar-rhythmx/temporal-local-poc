"""Temporal worker entrypoint."""

from __future__ import annotations

import asyncio
import os
import sys

from temporalio.client import Client
from temporalio.worker import Worker

# Import workflow from shared package copied at build time
from workflows.contracts import TASK_QUEUE
from workflows.patient_data_workflow import PatientDataWorkflow

from worker.activities import (
    format_patient,
    store_formatted_patient,
    store_raw_patient,
    validate_patient,
    write_audit_record,
)


async def main() -> None:
    temporal_host = os.environ.get(
        "TEMPORAL_ADDRESS", "temporal-frontend.temporal.svc.cluster.local:7233"
    )
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")

    client = await Client.connect(temporal_host, namespace=namespace)
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[PatientDataWorkflow],
        activities=[
            validate_patient,
            store_raw_patient,
            format_patient,
            store_formatted_patient,
            write_audit_record,
        ],
    )
    print(f"Worker polling task queue: {TASK_QUEUE}", flush=True)
    await worker.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
