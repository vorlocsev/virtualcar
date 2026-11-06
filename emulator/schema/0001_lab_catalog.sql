-- Virtual Car Lab Catalog v1: proposal / opt-in only, never executed at startup.
-- This database contains ONLY lab metadata and explicitly synthetic payloads.
-- Private donor captures must be encrypted sidecar files, never inline SQL.
-- Connections must enable PRAGMA foreign_keys=ON; migrations applied in transaction.
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY CHECK(version > 0),
    checksum_sha256 TEXT NOT NULL CHECK(length(checksum_sha256) = 64),
    applied_utc TEXT NOT NULL
);

CREATE TABLE vehicle_profiles (
    id TEXT PRIMARY KEY NOT NULL,
    label TEXT NOT NULL CHECK(length(label) BETWEEN 1 AND 96),
    platform TEXT NOT NULL CHECK(length(platform) BETWEEN 1 AND 40),
    model_year INTEGER CHECK(model_year BETWEEN 1900 AND 2200),
    provenance TEXT NOT NULL CHECK(provenance IN ('synthetic', 'captured_private', 'research_only')),
    created_utc TEXT NOT NULL
);

CREATE TABLE can_buses (
    id TEXT PRIMARY KEY NOT NULL,
    vehicle_profile_id TEXT NOT NULL REFERENCES vehicle_profiles(id) ON DELETE RESTRICT,
    label TEXT NOT NULL,
    bitrate INTEGER NOT NULL CHECK(bitrate IN (125000, 250000, 500000, 1000000)),
    id_format TEXT NOT NULL CHECK(id_format IN ('11bit', '29bit')),
    UNIQUE(vehicle_profile_id, label)
);

CREATE TABLE ecu_nodes (
    id TEXT PRIMARY KEY NOT NULL,
    bus_id TEXT NOT NULL REFERENCES can_buses(id) ON DELETE RESTRICT,
    label TEXT NOT NULL,
    transport TEXT NOT NULL CHECK(transport IN ('raw_can', 'iso15765', 'volvo_d2')),
    request_can_id INTEGER NOT NULL CHECK(request_can_id BETWEEN 0 AND 536870911),
    response_can_id INTEGER NOT NULL CHECK(response_can_id BETWEEN 0 AND 536870911),
    enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0, 1)),
    UNIQUE(bus_id, request_can_id, response_can_id, transport)
);

CREATE TABLE private_artifacts (
    id TEXT PRIMARY KEY NOT NULL,
    relative_path TEXT NOT NULL UNIQUE CHECK(length(relative_path) BETWEEN 1 AND 240),
    content_sha256 TEXT NOT NULL CHECK(length(content_sha256) = 64),
    size_bytes INTEGER NOT NULL CHECK(size_bytes BETWEEN 1 AND 1073741824),
    encryption TEXT NOT NULL CHECK(encryption IN ('dpapi_current_user')),
    kind TEXT NOT NULL CHECK(kind IN ('captured_trace', 'private_response')),
    created_utc TEXT NOT NULL
);

CREATE TABLE response_fixtures (
    id TEXT PRIMARY KEY NOT NULL,
    ecu_id TEXT NOT NULL REFERENCES ecu_nodes(id) ON DELETE RESTRICT,
    request_sha256 TEXT NOT NULL CHECK(length(request_sha256) = 64),
    provenance TEXT NOT NULL CHECK(provenance IN ('synthetic', 'captured_private')),
    lab_approval TEXT NOT NULL DEFAULT 'draft'
        CHECK(lab_approval IN ('draft', 'approved_for_readonly_lab')),
    synthetic_reply BLOB,
    private_artifact_id TEXT REFERENCES private_artifacts(id) ON DELETE RESTRICT,
    CHECK (
        (provenance = 'synthetic' AND synthetic_reply IS NOT NULL
         AND length(synthetic_reply) BETWEEN 1 AND 4128
         AND private_artifact_id IS NULL)
        OR
        (provenance = 'captured_private' AND synthetic_reply IS NULL
         AND private_artifact_id IS NOT NULL)
    )
);

CREATE TABLE scenarios (
    id TEXT PRIMARY KEY NOT NULL,
    label TEXT NOT NULL CHECK(length(label) BETWEEN 1 AND 96),
    vehicle_profile_id TEXT NOT NULL REFERENCES vehicle_profiles(id) ON DELETE RESTRICT,
    created_utc TEXT NOT NULL
);

CREATE TABLE scenario_revisions (
    id TEXT PRIMARY KEY NOT NULL,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL CHECK(revision > 0),
    sealed INTEGER NOT NULL DEFAULT 0 CHECK(sealed IN (0, 1)),
    snapshot_sha256 TEXT CHECK(snapshot_sha256 IS NULL OR length(snapshot_sha256) = 64),
    created_utc TEXT NOT NULL,
    CHECK(sealed = 0 OR snapshot_sha256 IS NOT NULL),
    UNIQUE(scenario_id, revision)
);

CREATE TABLE scenario_bindings (
    revision_id TEXT NOT NULL REFERENCES scenario_revisions(id) ON DELETE RESTRICT,
    fixture_id TEXT NOT NULL REFERENCES response_fixtures(id) ON DELETE RESTRICT,
    enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0, 1)),
    PRIMARY KEY(revision_id, fixture_id)
);

CREATE TABLE test_cases (
    id TEXT PRIMARY KEY NOT NULL,
    scenario_revision_id TEXT NOT NULL REFERENCES scenario_revisions(id) ON DELETE RESTRICT,
    category TEXT NOT NULL CHECK(category IN
        ('j2534_abi', 'can', 'iso_tp', 'uds_read', 'd2_read', 'ecu_inventory', 'fault', 'dvinholm_e2e')),
    assertion_json TEXT NOT NULL CHECK(length(assertion_json) BETWEEN 2 AND 16384),
    created_utc TEXT NOT NULL
);

CREATE TABLE test_runs (
    id TEXT PRIMARY KEY NOT NULL,
    test_case_id TEXT NOT NULL REFERENCES test_cases(id) ON DELETE RESTRICT,
    scenario_sha256 TEXT NOT NULL CHECK(length(scenario_sha256) = 64),
    dvinholm_commit TEXT,
    virtualcar_commit TEXT,
    j2534_dll_sha256 TEXT CHECK(j2534_dll_sha256 IS NULL OR length(j2534_dll_sha256) = 64),
    origin TEXT NOT NULL CHECK(origin IN ('synthetic_offline', 'vmware_virtual', 'physical_j2534')),
    status TEXT NOT NULL CHECK(status IN ('running', 'passed', 'failed', 'inconclusive', 'cancelled')),
    started_utc TEXT NOT NULL,
    finished_utc TEXT,
    failure_category TEXT,
    CHECK ((status = 'running' AND finished_utc IS NULL)
        OR (status <> 'running' AND finished_utc IS NOT NULL))
);

CREATE TABLE test_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES test_runs(id) ON DELETE CASCADE,
    elapsed_ns INTEGER NOT NULL CHECK(elapsed_ns >= 0),
    category TEXT NOT NULL CHECK(category IN
        ('j2534_open', 'j2534_close', 'can_tx', 'can_rx', 'iso_tp_fc',
         'response_delivered', 'missing_fixture', 'unsupported',
         'timeout', 'drop', 'scenario_reset', 'test_error')),
    count INTEGER NOT NULL DEFAULT 1 CHECK(count BETWEEN 0 AND 1000000)
);

CREATE INDEX idx_ecu_bus ON ecu_nodes(bus_id);
CREATE INDEX idx_fixtures_ecu_req ON response_fixtures(ecu_id, request_sha256);
CREATE INDEX idx_scenario_revisions ON scenario_revisions(scenario_id, revision);
CREATE INDEX idx_runs_case ON test_runs(test_case_id, started_utc);
CREATE INDEX idx_events_run_time ON test_events(run_id, elapsed_ns);

CREATE TRIGGER scenario_sealed_immutable
BEFORE UPDATE ON scenario_revisions
WHEN OLD.sealed = 1
BEGIN
    SELECT RAISE(ABORT, 'sealed scenario revision immutable');
END;

CREATE TRIGGER scenario_sealed_no_delete
BEFORE DELETE ON scenario_revisions
WHEN OLD.sealed = 1
BEGIN
    SELECT RAISE(ABORT, 'sealed scenario revision immutable');
END;

CREATE TRIGGER binding_no_insert_into_sealed
BEFORE INSERT ON scenario_bindings
WHEN (SELECT sealed FROM scenario_revisions WHERE id = NEW.revision_id) = 1
BEGIN
    SELECT RAISE(ABORT, 'sealed scenario bindings immutable');
END;

CREATE TRIGGER binding_no_update_in_sealed
BEFORE UPDATE ON scenario_bindings
WHEN (SELECT sealed FROM scenario_revisions WHERE id = OLD.revision_id) = 1
  OR (SELECT sealed FROM scenario_revisions WHERE id = NEW.revision_id) = 1
BEGIN
    SELECT RAISE(ABORT, 'sealed scenario bindings immutable');
END;

CREATE TRIGGER binding_no_delete_in_sealed
BEFORE DELETE ON scenario_bindings
WHEN (SELECT sealed FROM scenario_revisions WHERE id = OLD.revision_id) = 1
BEGIN
    SELECT RAISE(ABORT, 'sealed scenario bindings immutable');
END;

-- NOTE: A sealed revision requires an immutable compiled, hash-verified
-- snapshot artifact at runtime. These triggers protect revisions/bindings,
-- not all referenced ECU/profile rows; never compile from mutable rows
-- without verifying a materialized snapshot SHA-256.
