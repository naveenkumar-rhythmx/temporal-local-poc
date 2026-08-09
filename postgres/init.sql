-- Application PostgreSQL schema (NOT Temporal persistence).
-- Layer 1 (raw / RXCDM-like): patients, patient_events
-- Layer 2 (AIREADY-like):     air_* tables written by Temporal formatter activities
-- Idempotent: safe to re-run on every setup.

-- ---------------------------------------------------------------- raw layer
CREATE TABLE IF NOT EXISTS patients (
    patient_id      VARCHAR(64) PRIMARY KEY,
    mrn             VARCHAR(64),
    first_name      VARCHAR(128) NOT NULL,
    last_name       VARCHAR(128) NOT NULL,
    date_of_birth   DATE,
    gender          VARCHAR(32),
    status          VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE patients ADD COLUMN IF NOT EXISTS mrn VARCHAR(64);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS gender VARCHAR(32);
ALTER TABLE patients ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE TABLE IF NOT EXISTS patient_events (
    event_id        BIGSERIAL PRIMARY KEY,
    patient_id      VARCHAR(64) NOT NULL REFERENCES patients(patient_id),
    encounter_id    VARCHAR(64),
    event_type      VARCHAR(64) NOT NULL,
    payload         JSONB NOT NULL,
    source          VARCHAR(64) NOT NULL DEFAULT 'local-demo',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------ AIREADY layer
CREATE TABLE IF NOT EXISTS air_conditions (
    id              BIGSERIAL PRIMARY KEY,
    patient_id      VARCHAR(64) NOT NULL REFERENCES patients(patient_id),
    code            VARCHAR(32) NOT NULL,
    display         VARCHAR(256) NOT NULL,
    clinical_status VARCHAR(32) NOT NULL DEFAULT 'active',
    onset_date      DATE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (patient_id, code)
);

CREATE TABLE IF NOT EXISTS air_medications (
    id              BIGSERIAL PRIMARY KEY,
    patient_id      VARCHAR(64) NOT NULL REFERENCES patients(patient_id),
    name            VARCHAR(128) NOT NULL,
    drug_class      VARCHAR(64),
    dose            VARCHAR(64),
    route           VARCHAR(32),
    frequency       VARCHAR(32),
    status          VARCHAR(32) NOT NULL DEFAULT 'active',
    start_date      DATE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (patient_id, name)
);

CREATE TABLE IF NOT EXISTS air_allergies (
    id              BIGSERIAL PRIMARY KEY,
    patient_id      VARCHAR(64) NOT NULL REFERENCES patients(patient_id),
    substance       VARCHAR(128) NOT NULL,
    reaction        VARCHAR(256),
    severity        VARCHAR(32),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (patient_id, substance)
);

CREATE TABLE IF NOT EXISTS air_labs (
    id              BIGSERIAL PRIMARY KEY,
    patient_id      VARCHAR(64) NOT NULL REFERENCES patients(patient_id),
    code            VARCHAR(32) NOT NULL,
    display         VARCHAR(256) NOT NULL,
    value_num       NUMERIC(12,3),
    unit            VARCHAR(32),
    ref_low         NUMERIC(12,3),
    ref_high        NUMERIC(12,3),
    abnormal_flag   VARCHAR(16),
    collected_at    DATE NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (patient_id, code, collected_at)
);

CREATE TABLE IF NOT EXISTS air_vitals (
    id              BIGSERIAL PRIMARY KEY,
    patient_id      VARCHAR(64) NOT NULL REFERENCES patients(patient_id),
    systolic        INTEGER,
    diastolic       INTEGER,
    heart_rate      INTEGER,
    temp_c          NUMERIC(5,2),
    spo2            INTEGER,
    bmi             NUMERIC(5,2),
    recorded_at     DATE NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (patient_id, recorded_at)
);

CREATE TABLE IF NOT EXISTS air_appointments (
    id              BIGSERIAL PRIMARY KEY,
    patient_id      VARCHAR(64) NOT NULL REFERENCES patients(patient_id),
    encounter_id    VARCHAR(64),
    appt_type       VARCHAR(128) NOT NULL,
    provider        VARCHAR(128),
    scheduled_at    DATE,
    status          VARCHAR(32),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (patient_id, encounter_id, appt_type)
);

CREATE TABLE IF NOT EXISTS air_clinical_notes (
    id              BIGSERIAL PRIMARY KEY,
    patient_id      VARCHAR(64) NOT NULL REFERENCES patients(patient_id),
    encounter_id    VARCHAR(64),
    note_type       VARCHAR(64) NOT NULL,
    author          VARCHAR(128),
    summary         TEXT,
    full_text       TEXT,
    note_date       DATE NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (patient_id, encounter_id, note_type, note_date)
);

-- ------------------------------------------------- workflow output + audit
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
CREATE INDEX IF NOT EXISTS idx_air_labs_patient_collected ON air_labs(patient_id, collected_at DESC);
CREATE INDEX IF NOT EXISTS idx_air_vitals_patient_recorded ON air_vitals(patient_id, recorded_at DESC);
