namespace VirtualCar.Core;

/// <summary>
/// Serialized scenario and client-session lifecycle. No database, J2534,
/// CAN traffic, or machine-specific APIs in this assembly.
/// </summary>
public sealed class ScenarioCoordinator : IAsyncDisposable
{
    public const int MaximumSessions = 64;

    private readonly IScenarioCatalog _catalog;
    private readonly IScenarioRuntime _runtime;
    private readonly SemaphoreSlim _mutex = new(1, 1);
    private readonly Dictionary<ulong, ulong> _sessions = new();

    private ScenarioSnapshot? _selected;
    private ulong _generation;
    private ulong _nextSessionId;
    private bool _shutdown;

    public ScenarioCoordinator(IScenarioCatalog catalog, IScenarioRuntime runtime)
    {
        _catalog = catalog ?? throw new ArgumentNullException(nameof(catalog));
        _runtime = runtime ?? throw new ArgumentNullException(nameof(runtime));
    }

    public async Task SelectAsync(string id, long revision, CancellationToken cancellationToken = default)
    {
        await _mutex.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            EnsureRunning();
            if (_sessions.Count > 0)
                throw new InvalidOperationException("Cannot replace a scenario while sessions are active.");

            // Invalidate the previous selection before touching the runtime.
            _selected = null;
            _generation++;
            try
            {
                await _runtime.StopAsync(cancellationToken).ConfigureAwait(false);
                ScenarioCandidate? candidate = await _catalog.LoadAsync(id, revision, cancellationToken)
                    .ConfigureAwait(false);
                ScenarioSnapshot snapshot = ScenarioSnapshot.VerifySynthetic(candidate);
                if (snapshot.Id != id || snapshot.Revision != revision)
                    throw new InvalidOperationException("Laboratory scenario identity mismatch.");
                await _runtime.PrepareAsync(snapshot, cancellationToken).ConfigureAwait(false);
                cancellationToken.ThrowIfCancellationRequested();
                _selected = snapshot;
            }
            catch
            {
                // A partial native prepare may have occurred. Attempt best-effort
                // cleanup and never advertise the failed scenario as active.
                _selected = null;
                _generation++;
                try { await _runtime.StopAsync(CancellationToken.None).ConfigureAwait(false); }
                catch { /* Native teardown failure is not a successful session. */ }
                throw;
            }
        }
        finally { _mutex.Release(); }
    }

    public async Task<SessionToken> OpenSessionAsync(CancellationToken cancellationToken = default)
    {
        await _mutex.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            EnsureRunning();
            if (_selected is null)
                throw new InvalidOperationException("No verified synthetic scenario selected.");
            if (_sessions.Count >= MaximumSessions || _nextSessionId == ulong.MaxValue)
                throw new InvalidOperationException("Laboratory session limit reached.");

            ulong id = ++_nextSessionId;
            _sessions.Add(id, _generation);
            return new SessionToken(id, _generation);
        }
        finally { _mutex.Release(); }
    }

    public async Task ValidateSessionAsync(SessionToken token, CancellationToken cancellationToken = default)
    {
        await _mutex.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            EnsureRunning();
            if (!IsCurrent(token))
                throw new InvalidOperationException("Stale laboratory session.");
        }
        finally { _mutex.Release(); }
    }

    /// <summary>
    /// Return a COPY of strictly synthetic read fixture data only while the
    /// authenticated coordinator session and selected immutable scenario are
    /// current. No J2534, CAN, VIN lookup, or arbitrary request execution.
    /// </summary>
    public async Task<byte[]?> ReadSyntheticAsync(
        SessionToken token, uint requestCanId, uint responseCanId,
        bool extended, ushort did, CancellationToken cancellationToken = default)
    {
        await _mutex.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            EnsureRunning();
            if (!IsCurrent(token) || _selected is null)
                throw new InvalidOperationException("Stale laboratory session.");
            return SyntheticReadFixture.Find(
                _selected, requestCanId, responseCanId, extended, did);
        }
        finally { _mutex.Release(); }
    }

    public async Task CloseSessionAsync(SessionToken token, CancellationToken cancellationToken = default)
    {
        await _mutex.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            EnsureRunning();
            if (!IsCurrent(token))
                throw new InvalidOperationException("Stale laboratory session.");
            _sessions.Remove(token.Id);
        }
        finally { _mutex.Release(); }
    }

    public async Task ResetAsync(CancellationToken cancellationToken = default)
    {
        await _mutex.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            EnsureRunning();
            if (_sessions.Count > 0)
                throw new InvalidOperationException("Cannot reset a scenario with active sessions.");
            ScenarioSnapshot snapshot = _selected ??
                throw new InvalidOperationException("No scenario selected.");
            _selected = null;
            _generation++;
            try
            {
                await _runtime.StopAsync(cancellationToken).ConfigureAwait(false);
                await _runtime.PrepareAsync(snapshot, cancellationToken).ConfigureAwait(false);
                cancellationToken.ThrowIfCancellationRequested();
                _selected = snapshot;
            }
            catch
            {
                try { await _runtime.StopAsync(CancellationToken.None).ConfigureAwait(false); }
                catch { /* Nothing is advertised as active after this failure. */ }
                throw;
            }
        }
        finally { _mutex.Release(); }
    }

    public async Task ShutdownAsync(CancellationToken cancellationToken = default)
    {
        await _mutex.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (_shutdown) return;
            _shutdown = true;
            _selected = null;
            _generation++;
            _sessions.Clear();
            await _runtime.StopAsync(CancellationToken.None).ConfigureAwait(false);
        }
        finally { _mutex.Release(); }
    }

    public async Task<bool> HasSelectedScenarioAsync(CancellationToken cancellationToken = default)
    {
        await _mutex.WaitAsync(cancellationToken).ConfigureAwait(false);
        try { return !_shutdown && _selected is not null; }
        finally { _mutex.Release(); }
    }

    private bool IsCurrent(SessionToken token) =>
        _selected is not null && token.Id != 0 &&
        token.Generation == _generation &&
        _sessions.TryGetValue(token.Id, out ulong gen) && gen == token.Generation;

    private void EnsureRunning()
    {
        if (_shutdown)
            throw new ObjectDisposedException(nameof(ScenarioCoordinator));
    }

    public ValueTask DisposeAsync()
    {
        // Do not dispose the semaphore here: it would race with pending users.
        return new ValueTask(ShutdownAsync());
    }
}
