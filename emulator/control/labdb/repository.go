// Package labdb provides a fail-closed SQL metadata boundary for the
// Virtual Car test lab. It does not register a database driver, open an
// untrusted path, produce CAN replies, or enable a runtime scenario.
//
// The Windows x64 SQLite driver is selected in a separate integration stage.
// This code is compiled and tested with Go's standard library only.
package labdb

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"errors"
	"fmt"
	"regexp"
	"sync"
)

const (
	SchemaVersion = 1
	maxProfiles   = 100
)

var (
	ErrUnavailable = errors.New("lab database unavailable or invalid")
	ErrNotFound    = errors.New("sealed scenario revision not found")
	ErrInvalid    = errors.New("invalid lab metadata selector")
	idPattern     = regexp.MustCompile(`^[A-Za-z0-9_-]{1,96}$`)
	shaPattern    = regexp.MustCompile(`^[a-fA-F0-9]{64}$`)
)

// Repository owns only the injected database/sql connection. Its caller
// is responsible for opening the pinned SQLite driver with a fixed, validated
// local path, WAL, foreign_keys=ON on EVERY connection, and a single writer.
type Repository struct {
	db     *sql.DB
	mu     sync.RWMutex
	closed bool
}

type Profile struct {
	ID         string
	Label      string
	Platform   string
	ModelYear  sql.NullInt64
	Provenance string
}

type SealedRevision struct {
	ID                    string
	ScenarioID            string
	Revision              int64
	SnapshotSHA256        string
	VehicleProfileID      string
	Provenance            string
	SnapshotBytesVerified bool // Always false until stage 61 materialization
	RuntimeSelected       bool // Always false
	ProductionCompatible  bool // Always false
}

// Check uses the exact contents of schema/0001_lab_catalog.sql. It refuses
// a database with an unrecognized migration or failed integrity check.
func Check(ctx context.Context, db *sql.DB, schema []byte) (*Repository, error) {
	if db == nil || len(schema) == 0 || len(schema) > 128*1024 {
		return nil, ErrUnavailable
	}
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	var integrity string
	if err := db.QueryRowContext(ctx, "PRAGMA quick_check").Scan(&integrity); err != nil || integrity != "ok" {
		return nil, ErrUnavailable
	}
	var fk int
	if err := db.QueryRowContext(ctx, "PRAGMA foreign_keys").Scan(&fk); err != nil || fk != 1 {
		return nil, ErrUnavailable
	}
	// A single-connection injected driver is expected at this boundary.
	// Full pool DSN and connection pragma validation is stage 60B-2.
	var version int
	var checksum string
	rows, err := db.QueryContext(ctx, "SELECT version,checksum_sha256 FROM schema_migrations ORDER BY version")
	if err != nil {
		return nil, ErrUnavailable
	}
	defer rows.Close()
	count := 0
	for rows.Next() {
		count++
		if count > 1 || rows.Scan(&version, &checksum) != nil {
			return nil, ErrUnavailable
		}
	}
	if rows.Err() != nil || count != 1 || version != SchemaVersion {
		return nil, ErrUnavailable
	}
	sum := sha256.Sum256(schema)
	if checksum != hex.EncodeToString(sum[:]) {
		return nil, ErrUnavailable
	}
	// We only accept the schema/migration journal, not attested vehicle data.
	return &Repository{db: db}, nil
}

func validID(s string) bool { return idPattern.MatchString(s) }
func validHash(s string) bool { return shaPattern.MatchString(s) }

func (r *Repository) ListProfiles(ctx context.Context, limit int) ([]Profile, error) {
	if limit < 1 || limit > maxProfiles {
		return nil, ErrInvalid
	}
	r.mu.RLock()
	defer r.mu.RUnlock()
	if r.closed {
		return nil, ErrUnavailable
	}
	rows, err := r.db.QueryContext(ctx, `SELECT id,label,platform,model_year,provenance
		FROM vehicle_profiles ORDER BY id LIMIT ?`, limit)
	if err != nil {
		return nil, ErrUnavailable
	}
	defer rows.Close()
	result := make([]Profile, 0)
	for rows.Next() {
		var p Profile
		if err := rows.Scan(&p.ID, &p.Label, &p.Platform, &p.ModelYear, &p.Provenance); err != nil {
			return nil, ErrUnavailable
		}
		if !validID(p.ID) || len(p.Label) > 96 || len(p.Platform) > 40 {
			return nil, ErrUnavailable
		}
		result = append(result, p)
		if len(result) > limit {
			return nil, ErrUnavailable
		}
	}
	if rows.Err() != nil {
		return nil, ErrUnavailable
	}
	return result, nil
}

// GetSealedRevision returns metadata only. In particular the stored hash is
// NOT sufficient to authorize CAN/ECU responses. The materialized snapshot
// and its bytes must be verified separately, in a later stage.
func (r *Repository) GetSealedRevision(ctx context.Context, scenarioID string, revision int64) (SealedRevision, error) {
	if !validID(scenarioID) || revision <= 0 || revision > 1<<31-1 {
		return SealedRevision{}, ErrInvalid
	}
	r.mu.RLock()
	defer r.mu.RUnlock()
	if r.closed {
		return SealedRevision{}, ErrUnavailable
	}
	var s SealedRevision
	err := r.db.QueryRowContext(ctx, `SELECT sr.id,sr.scenario_id,sr.revision,sr.snapshot_sha256,
		sc.vehicle_profile_id,v.provenance FROM scenario_revisions sr
		JOIN scenarios sc ON sc.id=sr.scenario_id
		JOIN vehicle_profiles v ON v.id=sc.vehicle_profile_id
		WHERE sr.scenario_id=? AND sr.revision=? AND sr.sealed=1`,
		scenarioID, revision).Scan(&s.ID, &s.ScenarioID, &s.Revision,
		&s.SnapshotSHA256, &s.VehicleProfileID, &s.Provenance)
	if errors.Is(err, sql.ErrNoRows) {
		return SealedRevision{}, ErrNotFound
	}
	if err != nil || !validID(s.ID) || !validID(s.ScenarioID) ||
		!validID(s.VehicleProfileID) || !validHash(s.SnapshotSHA256) ||
		s.Revision != revision || s.ScenarioID != scenarioID ||
		(s.Provenance != "synthetic" && s.Provenance != "captured_private" && s.Provenance != "research_only") {
		return SealedRevision{}, ErrUnavailable
	}
	return s, nil
}

// Health returns aggregate counts but never VIN, raw logs, fixture bytes,
// private paths or any claim of hardware attestation.
func (r *Repository) Health(ctx context.Context) (map[string]any, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	if r.closed {
		return nil, ErrUnavailable
	}
	var p, sealed int64
	err := r.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM vehicle_profiles").Scan(&p)
	if err != nil {
		return nil, ErrUnavailable
	}
	err = r.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM scenario_revisions WHERE sealed=1").Scan(&sealed)
	if err != nil || p < 0 || sealed < 0 {
		return nil, ErrUnavailable
	}
	return map[string]any{
		"schema_version": SchemaVersion,
		"vehicle_profile_count": p,
		"sealed_scenario_count": sealed,
		"snapshot_bytes_verified": false,
		"actual_vehicle_accepted": false,
		"physical_j2534_verified": false,
	}, nil
}

// Close invalidates all new queries. The caller owns the injected sql.DB
// and must close it separately after all active calls return.
func (r *Repository) Close() {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.closed = true
}

// AssertNoRuntimeSelection is an explicit guard: do not silently coerce a
// metadata-only database lookup into a labcore.Catalog result.
func (r *Repository) AssertNoRuntimeSelection() error {
	return fmt.Errorf("stage60B SQL metadata cannot authorize a scenario: %w", ErrUnavailable)
}
