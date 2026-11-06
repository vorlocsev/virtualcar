// Package labdb owns the SQLite control-plane catalog for Virtual Car Lab.
// It never supplies ECU reply bytes or opens a database from the CAN hot path.
package labdb

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"errors"
	"net/url"
	"os"
	"path/filepath"
	"strings"

	"sectorv-virtualcar-control/labcore"

	_ "modernc.org/sqlite"
)

var (
	ErrExists    = errors.New("laboratory database already exists")
	ErrMigration = errors.New("laboratory schema version or checksum mismatch")
)
const maxDBBytes int64 = 64 * 1024 * 1024
const maxSchemaBytes int64 = 256 * 1024


type SQLiteCatalog struct {
	db *sql.DB
	repository *Repository
	schema []byte
}

type SQLiteHealth struct {
	Version int
	ProfileCount int
	SealedRevisions int
	ForeignKeyViolations int
	IntegrityOK bool
	PhysicalHardwareVerified bool
}

func validatePath(value string, exists bool) (string, error) {
	if value == "" || (strings.ContainsRune(value, rune(0)) || strings.ContainsAny(value, "?#")) {
		return "", ErrInvalid
	}
	p, err := filepath.Abs(value)
	if err != nil || strings.ToLower(filepath.Ext(p)) != ".db" {
		return "", ErrInvalid
	}
	if parent, err := os.Lstat(filepath.Dir(p)); err != nil || !parent.IsDir() || parent.Mode()&os.ModeSymlink != 0 {
		return "", ErrInvalid
	}
	file, err := os.Lstat(p)
	if exists {
		if err != nil || !file.Mode().IsRegular() || file.Size() > maxDBBytes {
			return "", ErrUnavailable
		}
	} else if err == nil || !errors.Is(err, os.ErrNotExist) {
		return "", ErrExists
	}
	return p, nil
}

func readSchema(path string) ([]byte, string, error) {
	if path == "" || filepath.Ext(path) != ".sql" {
		return nil, "", ErrInvalid
	}
	st, err := os.Lstat(path)
	if err != nil || !st.Mode().IsRegular() || st.Size() > maxSchemaBytes {
		return nil, "", ErrInvalid
	}
	sqlScript, err := os.ReadFile(path)
	if err != nil || len(sqlScript) == 0 || len(sqlScript) > int(maxSchemaBytes) {
		return nil, "", ErrInvalid
	}
	h := sha256.Sum256(sqlScript)
	return sqlScript, hex.EncodeToString(h[:]), nil
}

func openSQLite(ctx context.Context, path string) (*sql.DB, error) {
	// Build a file URI from a validated local path rather than accepting a
	// caller-controlled DSN, query, attached database, or driver pragma.
	abs := filepath.ToSlash(path)
	if filepath.VolumeName(path) != "" {
		abs = "/" + abs
	}
	uri := (&url.URL{Scheme: "file", Path: abs}).String()
	db, err := sql.Open("sqlite", uri)
	if err != nil { return nil, ErrUnavailable }
	db.SetMaxOpenConns(1)
	db.SetMaxIdleConns(1)
	db.SetConnMaxLifetime(0)
	for _, pragma := range []string {
		"PRAGMA trusted_schema=OFF",
		"PRAGMA foreign_keys=ON",
		"PRAGMA busy_timeout=5000",
		"PRAGMA journal_mode=WAL",
		"PRAGMA synchronous=FULL",
	} {
		if _, err = db.ExecContext(ctx, pragma); err != nil {
			db.Close()
			return nil, ErrUnavailable
		}
	}
	var fk int
	if err = db.QueryRowContext(ctx, "PRAGMA foreign_keys").Scan(&fk); err != nil || fk != 1 {
		db.Close()
		return nil, ErrUnavailable
	}
	return db, nil
}

// verify invokes the already-reviewed SQL metadata guard from stage 60B-1
// and additionally checks foreign-key integrity across the database.
func verify(ctx context.Context, db *sql.DB, schema []byte) (*Repository,error) {
	repo,err:=Check(ctx,db,schema)
	if err!=nil { return nil,err }
	rows,err:=db.QueryContext(ctx,"PRAGMA foreign_key_check")
	if err!=nil {return nil,ErrUnavailable}
	defer rows.Close()
	if rows.Next() || rows.Err()!=nil {return nil,ErrUnavailable}
	return repo,nil
}

// Initialize creates a brand-new local database exclusively and commits
// canonical v1 schema plus migration SHA in one transaction. No existing DB
// is overwritten, migrated, reset, or silently repaired.
func Initialize(ctx context.Context, dbPath, schemaPath string) (*SQLiteCatalog, error) {
	if err := ctx.Err(); err != nil { return nil, err }
	path, err := validatePath(dbPath, false)
	if err != nil { return nil, err }
	ddl, digest, err := readSchema(schemaPath)
	if err != nil { return nil, err }
	file, err := os.OpenFile(path, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if errors.Is(err, os.ErrExist) { return nil, ErrExists }
	if err != nil { return nil, ErrUnavailable }
	if err = file.Close(); err != nil { return nil, ErrUnavailable }
	created := true
	defer func() {
		if created {
			_ = os.Remove(path)
			_ = os.Remove(path+"-wal")
			_ = os.Remove(path+"-shm")
		}
	}()
	db, err := openSQLite(ctx, path)
	if err != nil { return nil, err }
	tx, err := db.BeginTx(ctx, nil)
	if err != nil { db.Close(); return nil, ErrUnavailable }
	// modernc SQLite supports scripts with CREATE TRIGGER ... BEGIN/END.
	if _, err = tx.ExecContext(ctx, string(ddl)); err == nil {
		_, err = tx.ExecContext(ctx,
			"INSERT INTO schema_migrations(version,checksum_sha256,applied_utc) VALUES(?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
			SchemaVersion, digest)
	}
	if err != nil { _ = tx.Rollback(); db.Close(); return nil, ErrMigration }
	if err = tx.Commit(); err != nil { db.Close(); return nil, ErrUnavailable }
	repo,verifyErr:=verify(ctx,db,ddl)
	if verifyErr!=nil {db.Close();return nil,verifyErr}
	created=false
	return &SQLiteCatalog{db:db,repository:repo,schema:ddl},nil
}

// Open verifies existing metadata against the unchanged v1 source migration.
// It intentionally does not auto-upgrade or replace the user's database.
func Open(ctx context.Context, dbPath, schemaPath string) (*SQLiteCatalog, error) {
	if err := ctx.Err(); err != nil { return nil, err }
	path, err := validatePath(dbPath, true)
	if err != nil { return nil, err }
	ddl, _, err := readSchema(schemaPath)
	if err != nil { return nil, err }
	db, err := openSQLite(ctx, path)
	if err != nil { return nil, err }
	repo,verifyErr:=verify(ctx,db,ddl)
	if verifyErr!=nil {db.Close();return nil,verifyErr}
	return &SQLiteCatalog{db:db,repository:repo,schema:ddl},nil
}
func (c *SQLiteCatalog) Close() error {
	c.repository.Close()
	return c.db.Close()
}

// ListProfiles reuses the stage60B-1 bounded metadata contract.
func (c *SQLiteCatalog) ListProfiles(ctx context.Context, limit int) ([]Profile,error) {
	return c.repository.ListProfiles(ctx,limit)
}

// LoadSealedSnapshot implements the labcore.Catalog boundary but never
// authorizes a response from metadata alone: no scenario bytes were verified.
func (c *SQLiteCatalog) LoadSealedSnapshot(ctx context.Context, id string, revision int64) (labcore.Snapshot,error) {
	record,err:=c.repository.GetSealedRevision(ctx,id,revision)
	if err!=nil {return labcore.Snapshot{},err}
	return labcore.Snapshot{
		ID:record.ScenarioID,
		Revision:record.Revision,
		SHA256:strings.ToLower(record.SnapshotSHA256),
		Provenance:record.Provenance,
		ApprovedReadOnly:false,
	},nil
}
var _ labcore.Catalog = (*SQLiteCatalog)(nil)

func (c *SQLiteCatalog) Health(ctx context.Context) (SQLiteHealth,error) {
	if _,err:=verify(ctx,c.db,c.schema);err!=nil {return SQLiteHealth{},err}
	h:=SQLiteHealth{Version:SchemaVersion,IntegrityOK:true,PhysicalHardwareVerified:false}
	if err:=c.db.QueryRowContext(ctx,"SELECT count(*) FROM vehicle_profiles").Scan(&h.ProfileCount);err!=nil{return SQLiteHealth{},ErrUnavailable}
	if err:=c.db.QueryRowContext(ctx,"SELECT count(*) FROM scenario_revisions WHERE sealed=1").Scan(&h.SealedRevisions);err!=nil{return SQLiteHealth{},ErrUnavailable}
	return h,nil
}

// Backup creates an independently consistent SQLite snapshot even in WAL mode.
// VACUUM INTO will write an exclusively reserved *empty* destination. This
// method does not change the source or copy just a potentially stale .db file.
func (c *SQLiteCatalog) Backup(ctx context.Context, destination string) error {
	if err := ctx.Err(); err != nil { return err }
	path,err:=validatePath(destination,false)
	if err != nil { return err }
	f,err:=os.OpenFile(path,os.O_CREATE|os.O_EXCL|os.O_WRONLY,0600)
	if errors.Is(err,os.ErrExist) { return ErrExists }
	if err!=nil { return ErrUnavailable }
	if err=f.Close();err!=nil { return ErrUnavailable }
	clean := true
	defer func(){if clean { _=os.Remove(path); _=os.Remove(path+"-wal");_ = os.Remove(path+"-shm") }}()
	if _,err=c.db.ExecContext(ctx,"VACUUM INTO ?",path);err!=nil{return ErrUnavailable}
	if st,err:=os.Stat(path);err!=nil || !st.Mode().IsRegular() {return ErrUnavailable}
	back,err:=openSQLite(ctx,path)
	if err!=nil {return err}
	defer back.Close()
	if _,err=verify(ctx,back,c.schema);err!=nil {return err}
	clean=false
	return nil
}
