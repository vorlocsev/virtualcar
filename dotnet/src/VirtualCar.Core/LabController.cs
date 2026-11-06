using System;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Threading;
using System.Threading.Tasks;

namespace VirtualCar.Core;

/// <summary>Where evidence came from. Never infer physical ECU support from this label.</summary>
public enum ScenarioOrigin
{
    Unknown = 0,
    Synthetic = 1,
    PrivateCapture = 2,
    ResearchOnly = 3
}

/// <summary>
/// Catalog returns raw materialized snapshot bytes, not an unverified database hash.
/// No SQLite/IO is permitted on the CAN receive hot path.
/// </summary>
public sealed record ScenarioSource(
    string ScenarioId,
    int Revision,
    string Sha256,
    ScenarioOrigin Origin,
    bool ApprovedForReadOnlyLab,
    byte[] Payload);

public sealed class VerifiedScenario
{
    private readonly byte[] _payload;

    internal VerifiedScenario(ScenarioSource source, byte[] snapshotCopy)
    {
        ScenarioId = source.ScenarioId;
        Revision = source.Revision;
        Sha256 = source.Sha256.ToLowerInvariant();
        Origin = source.Origin;
        _payload = snapshotCopy;
    }

    public string ScenarioId { get; }
    public int Revision { get; }
    public string Sha256 { get; }
    public ScenarioOrigin Origin { get; }
    public int PayloadSize => _payload.Length;

    // Return a copy to prevent mutation of bytes after verification.
    public byte[] ExportSnapshotCopy() => (byte[])_payload.Clone();
}

public interface IScenarioCatalog
{
    Task<ScenarioSource?> LoadMaterializedAsync(string id, int revision, CancellationToken cancellationToken);
}

/// <summary>
/// Runtime implementation must accept only read-only, allowlisted fixture operations.
/// This interface is not a J2534 implementation and never touches real hardware.
/// </summary>
public interface IScenarioRuntime
{
    Task PrepareAsync(VerifiedScenario scenario, CancellationToken cancellationToken);
    Task StopAsync(CancellationToken cancellationToken);
}

public readonly record struct SessionToken(Guid Id, long Generation);

public sealed class LabException(string message) : InvalidOperationException(message);

/// <summary>
/// Single-owner, fail-closed scenario/session control plane. Platform independent
/// so the same source can serve the future Windows x64 service and unit tests.
/// </summary>
public sealed class LabController(IScenarioCatalog catalog, IScenarioRuntime runtime) : IAsyncDisposable
{
    public const int MaxSessions = 64;
    public const int MaxSnapshotBytes = 1_048_576;

    private readonly SemaphoreSlim _gate = new(1, 1);
    private readonly HashSet<Guid> _sessions = [];
    private VerifiedScenario? _current;
    private long _generation;
    private bool _disposed;

    public async Task SelectAsync(string id, int revision, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(id) || id.Length > 96 || revision < 1)
            throw new LabException("Invalid scenario selector.");

        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            ThrowIfDisposed();
            if (_sessions.Count != 0)
                throw new LabException("Scenario selection blocked while diagnostic sessions are open.");

            // A previous runtime cannot be kept alive after a failed replacement.
            _current = null;
            _generation = checked(_generation + 1);
            await runtime.StopAsync(CancellationToken.None).ConfigureAwait(false);

            ScenarioSource? candidate = await catalog.LoadMaterializedAsync(id, revision, cancellationToken)
                .ConfigureAwait(false);
            VerifiedScenario checkedScenario = Validate(candidate, id, revision);

            // Failure leaves the controller without an active selection.
            await runtime.PrepareAsync(checkedScenario, cancellationToken).ConfigureAwait(false);
            _current = checkedScenario;
        }
        finally
        {
            _gate.Release();
        }
    }

    public async Task<SessionToken> OpenSessionAsync(CancellationToken cancellationToken = default)
    {
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            ThrowIfDisposed();
            if (_current is null)
                throw new LabException("No verified laboratory scenario selected.");
            if (_sessions.Count >= MaxSessions)
                throw new LabException("Maximum laboratory sessions reached.");
            Guid id;
            do { id = Guid.NewGuid(); } while (id == Guid.Empty || !_sessions.Add(id));
            return new SessionToken(id, _generation);
        }
        finally { _gate.Release(); }
    }

    public async Task ValidateSessionAsync(SessionToken token, CancellationToken cancellationToken = default)
    {
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            ThrowIfDisposed();
            if (_current is null || token.Generation != _generation ||
                token.Id == Guid.Empty || !_sessions.Contains(token.Id))
                throw new LabException("Stale or unknown diagnostic session.");
        }
        finally { _gate.Release(); }
    }

    public async Task CloseSessionAsync(SessionToken token, CancellationToken cancellationToken = default)
    {
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            ThrowIfDisposed();
            if (token.Generation != _generation || token.Id == Guid.Empty ||
                !_sessions.Remove(token.Id))
                throw new LabException("Stale or unknown diagnostic session.");
        }
        finally { _gate.Release(); }
    }

    public async Task ResetAsync(CancellationToken cancellationToken = default)
    {
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            ThrowIfDisposed();
            if (_sessions.Count != 0)
                throw new LabException("Reset blocked while diagnostic sessions are open.");
            VerifiedScenario selected = _current ??
                throw new LabException("No scenario available for reset.");
            _current = null;
            _generation = checked(_generation + 1);
            await runtime.StopAsync(CancellationToken.None).ConfigureAwait(false);
            await runtime.PrepareAsync(selected, cancellationToken).ConfigureAwait(false);
            _current = selected;
        }
        finally { _gate.Release(); }
    }

    public async Task<VerifiedScenario?> GetCurrentAsync(CancellationToken cancellationToken = default)
    {
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try { ThrowIfDisposed(); return _current; }
        finally { _gate.Release(); }
    }

    public async ValueTask DisposeAsync()
    {
        await _gate.WaitAsync().ConfigureAwait(false);
        try
        {
            if (_disposed) return;
            _disposed = true;
            _current = null;
            _sessions.Clear();
            _generation = checked(_generation + 1);
            await runtime.StopAsync(CancellationToken.None).ConfigureAwait(false);
        }
        finally { _gate.Release(); }
        // Semaphore intentionally not disposed: concurrent waiters will observe
        // _disposed and fail safely instead of faulting on a disposed semaphore.
    }

    private static VerifiedScenario Validate(ScenarioSource? source, string id, int revision)
    {
        if (source is null || source.ScenarioId != id || source.Revision != revision ||
            source.Revision < 1 ||
            (source.Origin != ScenarioOrigin.Synthetic && source.Origin != ScenarioOrigin.PrivateCapture) ||
            !source.ApprovedForReadOnlyLab || string.IsNullOrWhiteSpace(source.Sha256) ||
            source.Payload is null ||
            source.Payload.Length == 0 || source.Payload.Length > MaxSnapshotBytes)
            throw new LabException("Laboratory scenario was not approved or materialized.");

        byte[] copy = (byte[])source.Payload.Clone();
        byte[] expected;
        try { expected = Convert.FromHexString(source.Sha256); }
        catch (FormatException) { throw new LabException("Invalid scenario SHA-256."); }

        if (expected.Length != 32 || !CryptographicOperations.FixedTimeEquals(expected, SHA256.HashData(copy)))
            throw new LabException("Scenario materialized payload SHA-256 mismatch.");

        return new VerifiedScenario(source, copy);
    }

    private void ThrowIfDisposed()
    {
        if (_disposed) throw new ObjectDisposedException(nameof(LabController));
    }
}
