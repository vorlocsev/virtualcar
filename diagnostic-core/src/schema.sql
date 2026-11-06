-- Knowledge-only schema. No VIN, security credentials, PINs, or raw CAN payloads.
-- Do not automatically infer a supported operation from a research observation.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL PRIMARY KEY CHECK (version = 1),
    created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO schema_version (version) VALUES (1);

CREATE TABLE IF NOT EXISTS evidence_sources (
    id TEXT NOT NULL PRIMARY KEY,
    source_kind TEXT NOT NULL
        CHECK (source_kind IN ('public_document', 'public_code', 'private_observation', 'synthetic_test', 'manufacturer_document')),
    citation TEXT NOT NULL,
    license_note TEXT NOT NULL DEFAULT 'unknown',
    created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ecu_profiles (
    id TEXT NOT NULL PRIMARY KEY,
    platform TEXT NOT NULL,
    vehicle_model TEXT NOT NULL,
    ecu_name TEXT NOT NULL,
    bus_kind TEXT NOT NULL CHECK (bus_kind IN ('unknown', 'hs_can', 'ls_can', 'other')),
    tx_can_id INTEGER CHECK (tx_can_id IS NULL OR tx_can_id BETWEEN 0 AND 536870911),
    rx_can_id INTEGER CHECK (rx_can_id IS NULL OR rx_can_id BETWEEN 0 AND 536870911),
    evidence_status TEXT NOT NULL CHECK (evidence_status IN ('candidate', 'observed', 'verified', 'rejected')),
    source_id TEXT NOT NULL REFERENCES evidence_sources(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS diagnostic_services (
    id TEXT NOT NULL PRIMARY KEY,
    protocol TEXT NOT NULL CHECK (protocol IN ('uds', 'obd2', 'volvo_d2', 'unknown')),
    service_code INTEGER NOT NULL CHECK (service_code BETWEEN 0 AND 255),
    selector INTEGER CHECK (selector IS NULL OR selector BETWEEN 0 AND 65535),
    description TEXT NOT NULL,
    evidence_status TEXT NOT NULL CHECK (evidence_status IN ('candidate', 'observed', 'verified', 'rejected')),
    source_id TEXT NOT NULL REFERENCES evidence_sources(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS research_findings (
    id TEXT NOT NULL PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES evidence_sources(id) ON DELETE RESTRICT,
    ecu_profile_id TEXT REFERENCES ecu_profiles(id) ON DELETE SET NULL,
    service_id TEXT REFERENCES diagnostic_services(id) ON DELETE SET NULL,
    evidence_status TEXT NOT NULL CHECK (evidence_status IN ('candidate', 'observed', 'verified', 'rejected')),
    created_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ecu_platform ON ecu_profiles(platform, vehicle_model, ecu_name);
CREATE INDEX IF NOT EXISTS idx_services_protocol ON diagnostic_services(protocol, service_code, selector);
CREATE INDEX IF NOT EXISTS idx_findings_ecu ON research_findings(ecu_profile_id);
