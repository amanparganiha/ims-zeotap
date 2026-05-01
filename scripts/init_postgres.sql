-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Work Items (Source of Truth)
CREATE TABLE IF NOT EXISTS work_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component_id VARCHAR(255) NOT NULL,
    severity VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    title TEXT NOT NULL,
    signal_count INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    mttr_seconds INTEGER
);

-- RCA Records
CREATE TABLE IF NOT EXISTS rca_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id UUID NOT NULL REFERENCES work_items(id),
    incident_start TIMESTAMPTZ NOT NULL,
    incident_end TIMESTAMPTZ NOT NULL,
    root_cause_category VARCHAR(100) NOT NULL,
    fix_applied TEXT NOT NULL,
    prevention_steps TEXT NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Timeseries: signal aggregations (hypertable)
CREATE TABLE IF NOT EXISTS signal_metrics (
    time TIMESTAMPTZ NOT NULL,
    component_id VARCHAR(255) NOT NULL,
    signal_count INTEGER NOT NULL DEFAULT 1,
    severity VARCHAR(10)
);
SELECT create_hypertable('signal_metrics', 'time', if_not_exists => TRUE);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_work_items_status ON work_items(status);
CREATE INDEX IF NOT EXISTS idx_work_items_component ON work_items(component_id);
CREATE INDEX IF NOT EXISTS idx_work_items_severity ON work_items(severity);
CREATE INDEX IF NOT EXISTS idx_rca_work_item ON rca_records(work_item_id);
