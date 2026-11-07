package labcore

import (
    "context"
    "errors"
    "sync"
    "testing"
)

const testHash = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

type testCatalog struct {
    snapshot Snapshot
    err error
}

func (c *testCatalog) LoadSealedSnapshot(_ context.Context, _ string, _ int64) (Snapshot, error) {
    return c.snapshot, c.err
}

type testRuntime struct {
    mu sync.Mutex
    prepCount int
    stopCount int
    prepError error
    stopError error
}
func (r *testRuntime) Prepare(_ context.Context, _ Snapshot) error {
    r.mu.Lock(); defer r.mu.Unlock()
    r.prepCount++
    return r.prepError
}
func (r *testRuntime) Stop(_ context.Context) error {
    r.mu.Lock(); defer r.mu.Unlock()
    r.stopCount++
    return r.stopError
}

func newTestCore(t *testing.T) (*Core, *testCatalog, *testRuntime) {
    t.Helper()
    cat := &testCatalog{snapshot: Snapshot{
        ID: "lab-car", Revision: 1, SHA256: testHash, Provenance: "synthetic", ApprovedReadOnly: true,
    }}
    run := &testRuntime{}
    core, err := New(cat, run)
    if err != nil { t.Fatal(err) }
    return core, cat, run
}
func selectTest(t *testing.T, c *Core) {
    t.Helper()
    if err := c.Select(context.Background(), "lab-car", 1); err != nil { t.Fatal(err) }
}

func Test01InitialLifecycle(t *testing.T) {
    c, _, _ := newTestCore(t)
    if _, err := c.StartSession(); !errors.Is(err, ErrNotReady) { t.Fatalf("unready session: %v", err) }
    selectTest(t, c)
    if current, ok := c.Current(); !ok || current.ID != "lab-car" { t.Fatal("selection missing") }
}

func Test02RejectUnapprovedAndResearchFixtures(t *testing.T) {
    c, cat, _ := newTestCore(t)
    cat.snapshot.ApprovedReadOnly = false
    if err := c.Select(context.Background(), "lab-car", 1); !errors.Is(err, ErrNotReady) { t.Fatal(err) }
    cat.snapshot.ApprovedReadOnly = true
    cat.snapshot.Provenance = "research_only"
    if err := c.Select(context.Background(), "lab-car", 1); !errors.Is(err, ErrNotReady) { t.Fatal(err) }
    if _, ok := c.Current(); ok { t.Fatal("unsafe scenario selected") }
}

func Test03RejectUnverifiedHashesAndMismatchedRevisions(t *testing.T) {
    c, cat, _ := newTestCore(t)
    cat.snapshot.SHA256 = "fake-hash"
    if err := c.Select(context.Background(), "lab-car", 1); !errors.Is(err, ErrNotReady) { t.Fatal(err) }
    cat.snapshot.SHA256 = testHash
    cat.snapshot.Revision = 2
    if err := c.Select(context.Background(), "lab-car", 1); !errors.Is(err, ErrNotReady) { t.Fatal(err) }
}

func Test04SessionBlocksScenarioChangeAndReset(t *testing.T) {
    c, _, _ := newTestCore(t); selectTest(t, c)
    token, err := c.StartSession()
    if err != nil { t.Fatal(err) }
    if err := c.CheckSession(token); err != nil { t.Fatal(err) }
    if err := c.Select(context.Background(), "lab-car", 1); !errors.Is(err, ErrBusy) { t.Fatal(err) }
    if err := c.Reset(context.Background()); !errors.Is(err, ErrBusy) { t.Fatal(err) }
    if err := c.StopSession(token); err != nil { t.Fatal(err) }
    if err := c.Reset(context.Background()); err != nil { t.Fatal(err) }
    if _, err := c.StartSession(); err != nil { t.Fatal(err) }
}

func Test05ShutdownInvalidatesStaleTokens(t *testing.T) {
    c, _, run := newTestCore(t); selectTest(t, c)
    old, _ := c.StartSession()
    if err := c.Shutdown(context.Background()); err != nil { t.Fatal(err) }
    if err := c.CheckSession(old); !errors.Is(err, ErrStaleSession) { t.Fatal(err) }
    if _, err := c.StartSession(); !errors.Is(err, ErrNotReady) { t.Fatal(err) }
    if run.stopCount != 1 { t.Fatal("engine not stopped") }
}

func Test06RuntimePreparationFailureIsFailClosed(t *testing.T) {
    c, _, run := newTestCore(t); selectTest(t, c)
    run.prepError = errors.New("synthetic engine failure")
    if err := c.Select(context.Background(), "lab-car", 1); err == nil { t.Fatal("missing engine failure") }
    if _, ok := c.Current(); ok { t.Fatal("old fixture leaked after engine failure") }
}

func Test07ResetFailureIsFailClosed(t *testing.T) {
    c, _, run := newTestCore(t); selectTest(t, c)
    run.stopError = errors.New("synthetic stop failure")
    if err := c.Reset(context.Background()); err == nil { t.Fatal("missing reset failure") }
    if _, ok := c.Current(); ok { t.Fatal("old scene still active") }
    if _, err := c.StartSession(); !errors.Is(err, ErrNotReady) { t.Fatal(err) }
}

func Test08BoundedConcurrentSessionsAndGeneration(t *testing.T) {
    c, _, _ := newTestCore(t); selectTest(t, c)
    var wg sync.WaitGroup
    var mu sync.Mutex
    tokens := make([]SessionToken, 0, MaxSessions)
    var errs []error
    for i:=0; i<MaxSessions; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            token, err := c.StartSession()
            mu.Lock(); defer mu.Unlock()
            if err != nil { errs = append(errs, err) } else { tokens = append(tokens, token) }
        }()
    }
    wg.Wait()
    if len(errs)!=0 || len(tokens)!=MaxSessions { t.Fatalf("sessions=%d errors=%v",len(tokens),errs) }
    if _, err := c.StartSession(); !errors.Is(err, ErrMaxSessions) { t.Fatal(err) }
    for _, token := range tokens { if err := c.StopSession(token); err != nil { t.Fatal(err) } }
    if err := c.Reset(context.Background()); err != nil { t.Fatal(err) }
    for _, token := range tokens { if err := c.CheckSession(token); !errors.Is(err, ErrStaleSession) { t.Fatal(err) } }
}
