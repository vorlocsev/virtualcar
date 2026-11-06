package labdb

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"database/sql/driver"
	"encoding/hex"
	"errors"
	"io"
	"strings"
	"sync/atomic"
	"testing"
)

type stubState struct {
	fk       int64
	quick    string
	version  int64
	checksum string
	extra    bool
	missing  bool
	profiles bool
	sealed   bool
	badHash  bool
	fail     bool
	queries  atomic.Int64
}

type stubDriver struct{ state *stubState }
type stubConn struct{ state *stubState }
type stubRows struct {
	cols []string
	data [][]driver.Value
	idx int
}
func (d stubDriver) Open(_ string) (driver.Conn,error) { return &stubConn{d.state},nil }
func (c *stubConn) Prepare(string)(driver.Stmt,error) { return nil,errors.New("no prepares") }
func (c *stubConn) Close()error {return nil}
func (c *stubConn) Begin()(driver.Tx,error) {return nil,errors.New("no transactions")}
func (c *stubConn) QueryContext(ctx context.Context,q string,args []driver.NamedValue)(driver.Rows,error) {
	c.state.queries.Add(1)
	if err:=ctx.Err();err!=nil{return nil,err}
	if c.state.fail{return nil,errors.New("synthetic query failure")}
	s:=c.state
	switch {
	case q=="PRAGMA quick_check":
		return rows([]string{"quick_check"},[]driver.Value{s.quick}),nil
	case q=="PRAGMA foreign_keys":
		return rows([]string{"foreign_keys"},[]driver.Value{s.fk}),nil
	case strings.HasPrefix(q,"SELECT version,checksum_sha256 FROM schema_migrations"):
		if s.missing{return &stubRows{cols:[]string{"version","checksum_sha256"}},nil}
		res:=rows([]string{"version","checksum_sha256"},[]driver.Value{s.version,s.checksum})
		if s.extra{res.data=append(res.data,[]driver.Value{int64(2),s.checksum})}
		return res,nil
	case strings.Contains(q,"FROM vehicle_profiles ORDER BY id LIMIT ?"):
		if !s.profiles{return &stubRows{cols:[]string{"id","label","platform","model_year","provenance"}},nil}
		return rows([]string{"id","label","platform","model_year","provenance"},
			[]driver.Value{"lab","Synthetic car","GENERIC",int64(2009),"synthetic"}),nil
	case strings.Contains(q,"FROM scenario_revisions sr"):
		if !s.sealed{return &stubRows{cols:[]string{"id","scenario_id","revision","snapshot_sha256","vehicle_profile_id","provenance"}},nil}
		hash:=strings.Repeat("a",64)
		if s.badHash{hash="bad"}
		return rows([]string{"id","scenario_id","revision","snapshot_sha256","vehicle_profile_id","provenance"},
			[]driver.Value{"revision","scenario",int64(1),hash,"lab","synthetic"}),nil
	case q=="SELECT COUNT(*) FROM vehicle_profiles":
		return rows([]string{"count"},[]driver.Value{int64(1)}),nil
	case q=="SELECT COUNT(*) FROM scenario_revisions WHERE sealed=1":
		return rows([]string{"count"},[]driver.Value{int64(1)}),nil
	default:
		return nil,errors.New("unexpected SQL")
	}
}
func rows(cols []string, data ...[]driver.Value)*stubRows{return &stubRows{cols:cols,data:data}}
func (r *stubRows) Columns()[]string{return r.cols}
func (r *stubRows) Close()error{return nil}
func (r *stubRows) Next(dst []driver.Value)error{
	if r.idx==len(r.data){return io.EOF}
	copy(dst,r.data[r.idx]);r.idx++;return nil
}

var driverCounter atomic.Int64
var schema = []byte("SYNTHETIC-LOCAL-SCHEMA-V1")
func build(t *testing.T,opts func(*stubState))(*Repository,*stubState){
	t.Helper()
	hash:=sha256.Sum256(schema)
	state:=&stubState{fk:1,quick:"ok",version:1,checksum:hex.EncodeToString(hash[:])}
	if opts!=nil{opts(state)}
	name:="lab-sql-stub-"+string(rune(65+driverCounter.Add(1)))
	sql.Register(name,stubDriver{state})
	db,err:=sql.Open(name,"local-only")
	if err!=nil{t.Fatal(err)}
	db.SetMaxOpenConns(1)
	t.Cleanup(func(){db.Close()})
	repo,err:=Check(context.Background(),db,schema)
	if err!=nil{t.Fatalf("check: %v",err)}
	return repo,state
}

func Test01MigrationChecksumAndSingleRevision(t *testing.T){
	r,s:=build(t,nil)
	defer r.Close()
	if s.queries.Load()!=3{t.Fatalf("expected 3 integrity queries, got %d",s.queries.Load())}
}
func Test02RejectCorruptAndUnknownMigration(t *testing.T){
	for _,mutate:=range []func(*stubState){
		func(s *stubState){s.quick="corrupt"},
		func(s *stubState){s.version=2},
		func(s *stubState){s.extra=true},
		func(s *stubState){s.missing=true},
		func(s *stubState){s.checksum=strings.Repeat("f",64)},
		func(s *stubState){s.fk=0},
	}{
		hash:=sha256.Sum256(schema)
		s:=&stubState{fk:1,quick:"ok",version:1,checksum:hex.EncodeToString(hash[:])}
		mutate(s)
		name:="reject-sql-stub-"+string(rune(100+driverCounter.Add(1)))
		sql.Register(name,stubDriver{s})
		db,_:=sql.Open(name,"local")
		db.SetMaxOpenConns(1)
		_,err:=Check(context.Background(),db,schema)
		db.Close()
		if !errors.Is(err,ErrUnavailable){t.Fatalf("unexpected error: %v",err)}
	}
}
func Test03ReadSyntheticProfileMetadata(t *testing.T){
	r,_:=build(t,func(s *stubState){s.profiles=true})
	profiles,err:=r.ListProfiles(context.Background(),25)
	if err!=nil || len(profiles)!=1 || profiles[0].ID!="lab"{t.Fatalf("%v %v",profiles,err)}
	if _,err=r.ListProfiles(context.Background(),101);!errors.Is(err,ErrInvalid){t.Fatal(err)}
}
func Test04SealedDescriptorIsNotVerified(t *testing.T){
	r,_:=build(t,func(s *stubState){s.sealed=true})
	found,err:=r.GetSealedRevision(context.Background(),"scenario",1)
	if err!=nil{t.Fatal(err)}
	if found.SnapshotBytesVerified || found.RuntimeSelected || found.ProductionCompatible{
		t.Fatal("metadata must not become verified")
	}
	if err=r.AssertNoRuntimeSelection();!errors.Is(err,ErrUnavailable){t.Fatal(err)}
}
func Test05AbsentAndTamperedDescriptor(t *testing.T){
	r,_:=build(t,nil)
	if _,err:=r.GetSealedRevision(context.Background(),"scenario",1);!errors.Is(err,ErrNotFound){t.Fatal(err)}
	r2,_:=build(t,func(s *stubState){s.sealed=true;s.badHash=true})
	if _,err:=r2.GetSealedRevision(context.Background(),"scenario",1);!errors.Is(err,ErrUnavailable){t.Fatal(err)}
}
func Test06SelectorsParameterizedAndBounded(t *testing.T){
	r,s:=build(t,func(s *stubState){s.sealed=true})
	base:=s.queries.Load()
	for _,id:=range []string{"","bad' OR 1=1 --",strings.Repeat("x",97)}{
		if _,err:=r.GetSealedRevision(context.Background(),id,1);!errors.Is(err,ErrInvalid){t.Fatal(err)}
	}
	if _,err:=r.GetSealedRevision(context.Background(),"scenario",-1);!errors.Is(err,ErrInvalid){t.Fatal(err)}
	if s.queries.Load()!=base{t.Fatal("bad selectors reached database")}
}
func Test07CancellationAndInjectedFailure(t *testing.T){
	r,_:=build(t,nil)
	ctx,cancel:=context.WithCancel(context.Background());cancel()
	if _,err:=r.ListProfiles(ctx,10);err==nil{t.Fatal("cancelled query succeeded")}
	r2,state:=build(t,nil)
	state.fail=true
	if _,err:=r2.Health(context.Background());!errors.Is(err,ErrUnavailable){t.Fatal(err)}
}
func Test08CloseAndSafeHealthOnly(t *testing.T){
	r,_:=build(t,nil)
	h,err:=r.Health(context.Background())
	if err!=nil{t.Fatal(err)}
	for _,k:=range []string{"vin","pin","eeprom","private_path","raw_payload"}{
		if _,ok:=h[k];ok{t.Fatalf("unsafe health key: %s",k)}
	}
	if h["physical_j2534_verified"]!=false{t.Fatal("synthetic proof was elevated")}
	r.Close()
	if _,err:=r.Health(context.Background());!errors.Is(err,ErrUnavailable){t.Fatal(err)}
}
