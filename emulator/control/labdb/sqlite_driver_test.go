package labdb

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"

	"sectorv-virtualcar-control/labcore"
)

const fakeDigest = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
const syntheticTime = "2026-11-06T00:00:00Z"

func schemaPath() string {
	return filepath.Join("..", "..", "schema", "0001_lab_catalog.sql")
}
func makeDB(t *testing.T) (*SQLiteCatalog, string) {
	t.Helper()
	path := filepath.Join(t.TempDir(), "lab.db")
	c, err := Initialize(context.Background(), path, schemaPath())
	if err != nil { t.Fatalf("initialize: %v", err) }
	t.Cleanup(func(){ _=c.Close() })
	return c,path
}
func seedMetadata(t *testing.T, c *SQLiteCatalog) {
	t.Helper()
	ctx:=context.Background()
	tx,err:=c.db.BeginTx(ctx,nil)
	if err!=nil {t.Fatal(err)}
	for _, entry:= range []struct{query string; args []any}{
		{"INSERT INTO vehicle_profiles VALUES(?,?,?,?,?,?)",[]any{"lab","Synthetic car","GENERIC",2009,"synthetic",syntheticTime}},
		{"INSERT INTO scenarios VALUES(?,?,?,?)",[]any{"scene","Synthetic smoke","lab",syntheticTime}},
		{"INSERT INTO scenario_revisions VALUES(?,?,?,?,?,?)",[]any{"rev","scene",1,1,fakeDigest,syntheticTime}},
	} {
		if _,err=tx.ExecContext(ctx,entry.query,entry.args...);err!=nil {_=tx.Rollback();t.Fatalf("seed: %v",err)}
	}
	if err=tx.Commit();err!=nil {t.Fatal(err)}
}

func Test01InitializeAndReopenValidatesMigration(t *testing.T) {
	c,path:=makeDB(t)
	health,err:=c.Health(context.Background())
	if err!=nil || !health.IntegrityOK || health.Version!=1 || health.PhysicalHardwareVerified {t.Fatalf("health: %+v %v",health,err)}
	r,err:=Open(context.Background(),path,schemaPath())
	if err!=nil {t.Fatal(err)}
	defer r.Close()
	var fk int
	if err=r.db.QueryRow("PRAGMA foreign_keys").Scan(&fk);err!=nil||fk!=1 {t.Fatalf("foreign_keys=%d err=%v",fk,err)}
	if r.db.Stats().MaxOpenConnections!=1 {t.Fatal("unbounded database pool")}
}

func Test02MissingDatabaseNoImplicitCreationAndNoOverwrite(t *testing.T) {
	path:=filepath.Join(t.TempDir(),"lab.db")
	if _,err:=Open(context.Background(),path,schemaPath());!errors.Is(err,ErrUnavailable) {t.Fatalf("missing DB: %v",err)}
	c,err:=Initialize(context.Background(),path,schemaPath())
	if err!=nil {t.Fatal(err)}
	defer c.Close()
	if _,err=Initialize(context.Background(),path,schemaPath());!errors.Is(err,ErrExists) {t.Fatalf("overwrite allowed: %v",err)}
}

func Test03RejectMigrationTamperingAndCorruption(t *testing.T) {
	c,path:=makeDB(t)
	if _,err:=c.db.Exec("UPDATE schema_migrations SET checksum_sha256=?",strings.Repeat("f",64));err!=nil{t.Fatal(err)}
	if _,err:=Open(context.Background(),path,schemaPath());!errors.Is(err,ErrUnavailable){t.Fatalf("tampered schema: %v",err)}
	if err:=c.Close();err!=nil {t.Fatal(err)}
	// A corrupt user DB is never implicitly destroyed or reset.
	corrupt:=filepath.Join(t.TempDir(),"bad.db")
	if err:=os.WriteFile(corrupt,[]byte("not sqlite"),0600);err!=nil{t.Fatal(err)}
	if _,err:=Open(context.Background(),corrupt,schemaPath());err==nil{t.Fatal("corrupt DB accepted")}
	body,err:=os.ReadFile(corrupt)
	if err!=nil || string(body)!="not sqlite" {t.Fatal("corrupt source overwritten")}
}

type inertRuntime struct{}
func (*inertRuntime) Prepare(context.Context, labcore.Snapshot) error {return nil}
func (*inertRuntime) Stop(context.Context) error {return nil}

func Test04SealedMetadataCannotAuthorizeLabcoreResponse(t *testing.T) {
	c,_:=makeDB(t)
	seedMetadata(t,c)
	s,err:=c.LoadSealedSnapshot(context.Background(),"scene",1)
	if err!=nil || s.SHA256!=fakeDigest || s.ApprovedReadOnly {t.Fatalf("unverified metadata: %+v %v",s,err)}
	core,err:=labcore.New(c,&inertRuntime{})
	if err!=nil{t.Fatal(err)}
	if err=core.Select(context.Background(),"scene",1);!errors.Is(err,labcore.ErrNotReady) {t.Fatalf("metadata authorized replay: %v",err)}
	if _,active:=core.Current();active {t.Fatal("unverified replay activated")}
}

func Test05BoundedSelectorsAndNoReplyLeak(t *testing.T) {
	c,_:=makeDB(t)
	seedMetadata(t,c)
	profiles,err:=c.ListProfiles(context.Background(),10)
	if err!=nil || len(profiles)!=1 || profiles[0].ID!="lab" {t.Fatalf("profiles: %+v %v",profiles,err)}
	if _,err=c.ListProfiles(context.Background(),101);!errors.Is(err,ErrInvalid) {t.Fatal("oversized listing")}
	if _,err=c.LoadSealedSnapshot(context.Background(),"scene'; DROP TABLE scenarios;--",1);!errors.Is(err,ErrInvalid){t.Fatal("unsafe selector accepted")}
	if _,err=c.LoadSealedSnapshot(context.Background(),"scene",2);!errors.Is(err,ErrNotFound){t.Fatal("missing revision accepted")}
	if _,err=c.LoadSealedSnapshot(context.Background(),"scene",-2);!errors.Is(err,ErrInvalid){t.Fatal("bad revision")}
	if h,err:=c.Health(context.Background());err!=nil || h.ProfileCount!=1 {t.Fatalf("database altered: %+v %v",h,err)}
}

func Test06BackupIsConsistentAcrossWALWrites(t *testing.T) {
	c,_:=makeDB(t)
	seedMetadata(t,c)
	backupPath:=filepath.Join(t.TempDir(),"backup.db")
	if err:=c.Backup(context.Background(),backupPath);err!=nil {t.Fatalf("WAL backup: %v",err)}
	if err:=c.Backup(context.Background(),backupPath);!errors.Is(err,ErrExists) {t.Fatalf("backup overwrite: %v",err)}
	_,err:=c.db.Exec("INSERT INTO vehicle_profiles VALUES(?,?,?,?,?,?)","after-backup","Synthetic 2","GENERIC",2009,"synthetic",syntheticTime)
	if err!=nil {t.Fatal(err)}
	back,err:=Open(context.Background(),backupPath,schemaPath())
	if err!=nil {t.Fatalf("backup unavailable: %v",err)}
	defer back.Close()
	h,err:=back.Health(context.Background())
	if err!=nil || h.ProfileCount!=1 || h.SealedRevisions!=1 {t.Fatalf("inconsistent backup %+v %v",h,err)}
}

func Test07CancellationAndConcurrentMetadataReaders(t *testing.T) {
	c,_:=makeDB(t)
	seedMetadata(t,c)
	ctx,cancel:=context.WithCancel(context.Background())
	cancel()
	if _,err:=c.LoadSealedSnapshot(ctx,"scene",1);!errors.Is(err,ErrUnavailable) && !errors.Is(err,context.Canceled) {t.Fatalf("cancellation: %v",err)}
	var wg sync.WaitGroup
	fail:=make(chan error,30)
	for i:=0;i<30;i++ {
		wg.Add(1)
		go func(){
			defer wg.Done()
			rows,err:=c.ListProfiles(context.Background(),1)
			if err!=nil {fail<-err;return}
			if len(rows)!=1 {fail<-errors.New("wrong profile count")}
		}()
	}
	wg.Wait()
	close(fail)
	for err:=range fail {t.Fatal(err)}
}

func Test08SymlinkRejectionAndForeignKeys(t *testing.T) {
	c,path:=makeDB(t)
	alias:=filepath.Join(t.TempDir(),"alias.db")
	if err:=os.Symlink(path,alias);err==nil {
		if _,err:=Open(context.Background(),alias,schemaPath());!errors.Is(err,ErrUnavailable) && !errors.Is(err,ErrInvalid) {t.Fatalf("symlink accepted: %v",err)}
	}
	_,err:=c.db.Exec("INSERT INTO can_buses VALUES(?,?,?,?,?)","bus","missing","HS",500000,"11bit")
	if err==nil {t.Fatal("foreign key not enforced")}
	h,err:=c.Health(context.Background())
	if err!=nil || h.ForeignKeyViolations!=0 || !h.IntegrityOK {t.Fatalf("integrity: %+v %v",h,err)}
}
