-- Application PostgreSQL schema (NOT Temporal persistence).
-- Mirrors conceptual tables used by patient-data-services + DES formatters.

CREATE TABLE IF NOT EXISTS patients (
    patient_id      VARCHAR(64) PRIMARY KEY,
    first_name      VARCHAR(128) NOT NULL,
    last_name       VARCHAR(128) NOT NULL,
    date_of_birth   DATE,
    status          VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS patient_events (
    event_id        BIGSERIAL PRIMARY KEY,
    patient_id      VARCHAR(64) NOT NULL REFERENCES patients(patient_id),
    encounter_id    VARCHAR(64),
    event_type      VARCHAR(64) NOT NULL,
    payload         JSONB NOT NULL,
    source          VARCHAR(64) NOT NULL DEFAULT 'local-demo',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS formatted_patient_data (
    id              BIGSERIAL PRIMARY KEY,
    patient_id      VARCHAR(64) NOT NULL REFERENCES patients(patient_id),
    workflow_id     VARCHAR(256) NOT NULL,
    format_version  VARCHAR(16) NOT NULL DEFAULT 'v1',
    formatted_json  JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_execution_audit (
    id              BIGSERIAL PRIMARY KEY,
    workflow_id     VARCHAR(256) NOT NULL,
    run_id          VARCHAR(128),
    patient_id      VARCHAR(64),
    status          VARCHAR(32) NOT NULL,
    detail          JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_patient_events_patient_id ON patient_events(patient_id);
CREATE INDEX IF NOT EXISTS idx_formatted_patient_data_patient_id ON formatted_patient_data(patient_id);
CREATE INDEX IF NOT EXISTS idx_workflow_audit_workflow_id ON workflow_execution_audit(workflow_id);
