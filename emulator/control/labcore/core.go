package labcore

import (
    "context"
    "errors"
    "fmt"
    "sync"
)

var (
    ErrBusy = errors.New("lab core has active J2534 sessions")
    ErrNotReady = errors.New("lab core has no verified read-only scenario")
    ErrStaleSession = errors.New("stale laboratory J2534 session")
    ErrMaxSessions = errors.New("laboratory session limit exceeded")
)

const MaxSessions = 64

// Snapshot is an immutable, hash-verified read-only scenario descriptor.
// The application must validate the underlying materialized artifact bytes
// against SHA256 before activating it. This core never loads SQL on the CAN path.
type Snapshot struct {
    ID string
    Revision int64
    SHA256 string
    Provenance string // synthetic or captured_private, never research_only
    ApprovedReadOnly bool
}

type Catalog interface {
    LoadSealedSnapshot(context.Context, string, int64) (Snapshot, error)
}

type Runtime interface {
    // Prepare and Stop are read-only lab operations, never real vehicle writes.
    Prepare(context.Context, Snapshot) error
    Stop(context.Context) error
}

type SessionToken struct {
    ID uint64
    Generation uint64
}

type Core struct {
    mu sync.Mutex
    catalog Catalog
    runtime Runtime
    selected *Snapshot
    generation uint64
    nextSession uint64
    active map[uint64]uint64
}

func New(catalog Catalog, runtime Runtime) (*Core, error) {
    if catalog == nil || runtime == nil {
        return nil, errors.New("lab catalog and engine are required")
    }
    return &Core{catalog: catalog, runtime: runtime, active: make(map[uint64]uint64)}, nil
}

func isSHA256(s string) bool {
    if len(s) != 64 { return false }
    for _, ch := range s {
        if (ch < '0' || ch > '9') && (ch < 'a' || ch > 'f') && (ch < 'A' || ch > 'F') { return false }
    }
    return true
}

func validate(s Snapshot, id string, revision int64) error {
    if s.ID != id || s.Revision != revision || revision < 1 ||
       !isSHA256(s.SHA256) || !s.ApprovedReadOnly ||
       (s.Provenance != "synthetic" && s.Provenance != "captured_private") {
        return ErrNotReady
    }
    return nil
}

// Select forbids scenario changes while a diagnostic client has open sessions.
func (c *Core) Select(ctx context.Context, id string, revision int64) error {
    c.mu.Lock()
    defer c.mu.Unlock()
    if err := ctx.Err(); err != nil { return err }
    if len(c.active) != 0 { return ErrBusy }
    if len(id) == 0 || len(id) > 128 || revision < 1 { return ErrNotReady }
    snapshot, err := c.catalog.LoadSealedSnapshot(ctx, id, revision)
    if err != nil { return fmt.Errorf("load lab scenario: %w", err) }
    if err := validate(snapshot, id, revision); err != nil { return err }
    // A failed preparation may have partially altered the runtime.
    // Invalidate the old selection and all reply generations fail-closed.
    if err := c.runtime.Prepare(ctx, snapshot); err != nil {
        c.selected = nil
        c.generation++
        return fmt.Errorf("prepare lab scenario: %w", err)
    }
    c.selected = &snapshot
    c.generation++
    return nil
}

func (c *Core) StartSession() (SessionToken, error) {
    c.mu.Lock()
    defer c.mu.Unlock()
    if c.selected == nil { return SessionToken{}, ErrNotReady }
    if len(c.active) >= MaxSessions { return SessionToken{}, ErrMaxSessions }
    c.nextSession++
    if c.nextSession == 0 { return SessionToken{}, ErrMaxSessions }
    c.active[c.nextSession] = c.generation
    return SessionToken{ID: c.nextSession, Generation: c.generation}, nil
}

func (c *Core) CheckSession(token SessionToken) error {
    c.mu.Lock()
    defer c.mu.Unlock()
    if token.ID == 0 || token.Generation != c.generation ||
       c.active[token.ID] != token.Generation || c.selected == nil {
        return ErrStaleSession
    }
    return nil
}

func (c *Core) StopSession(token SessionToken) error {
    c.mu.Lock()
    defer c.mu.Unlock()
    if token.ID == 0 || token.Generation != c.generation ||
       c.active[token.ID] != token.Generation {
        return ErrStaleSession
    }
    delete(c.active, token.ID)
    return nil
}

// Reset requires zero sessions so stale queued CAN data cannot cross a reset.
func (c *Core) Reset(ctx context.Context) error {
    c.mu.Lock()
    defer c.mu.Unlock()
    if err := ctx.Err(); err != nil { return err }
    if len(c.active) > 0 { return ErrBusy }
    if c.selected == nil { return ErrNotReady }
    current := *c.selected
    c.selected = nil
    c.generation++
    if err := c.runtime.Stop(ctx); err != nil { return fmt.Errorf("stop lab engine: %w", err) }
    if err := c.runtime.Prepare(ctx, current); err != nil { return fmt.Errorf("reset lab engine: %w", err) }
    c.selected = &current
    return nil
}

// Shutdown invalidates generations first even when the runtime fails to stop.
func (c *Core) Shutdown(ctx context.Context) error {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.selected = nil
    c.active = make(map[uint64]uint64)
    c.generation++
    return c.runtime.Stop(ctx)
}

func (c *Core) Current() (Snapshot, bool) {
    c.mu.Lock()
    defer c.mu.Unlock()
    if c.selected == nil { return Snapshot{}, false }
    return *c.selected, true
}
