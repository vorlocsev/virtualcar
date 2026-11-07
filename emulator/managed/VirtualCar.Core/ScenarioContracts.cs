using System.Security.Cryptography;
using System.Text.RegularExpressions;

namespace VirtualCar.Core;

/// <summary>Only synthetic scenarios are permitted during migration M0.
/// Captured or research evidence must never activate ECU replies by accident.</summary>
public enum ScenarioProvenance
{
    Synthetic,
    CapturedPrivate,
    ResearchOnly
}

/// <summary>A draft returned by a catalog. The caller does not trust this metadata.</summary>
public sealed record ScenarioCandidate(
    string Id,
    long Revision,
    ScenarioProvenance Provenance,
    bool ApprovedReadOnly,
    byte[] CanonicalBytes,
    string Sha256);

/// <summary>Validated, immutable private copy of a synthetic laboratory payload.</summary>
public sealed class ScenarioSnapshot
{
    private static readonly Regex IdentifierPattern = new(
        "^[A-Za-z0-9_-]{1,96}$",
        RegexOptions.Compiled | RegexOptions.CultureInvariant,
        TimeSpan.FromMilliseconds(100));

    private readonly byte[] _bytes;

    private ScenarioSnapshot(string id, long revision, byte[] canonicalBytes, string sha256)
    {
        Id = id;
        Revision = revision;
        _bytes = canonicalBytes;
        Sha256 = sha256;
    }

    public string Id { get; }
    public long Revision { get; }
    public string Sha256 { get; }
    public ScenarioProvenance Provenance => ScenarioProvenance.Synthetic;
    public bool ApprovedReadOnly => true;
    public ReadOnlySpan<byte> CanonicalBytes => _bytes;

    public static ScenarioSnapshot VerifySynthetic(ScenarioCandidate? candidate)
    {
        if (candidate is null ||
            string.IsNullOrWhiteSpace(candidate.Id) ||
            !IdentifierPattern.IsMatch(candidate.Id) ||
            candidate.Revision <= 0 ||
            candidate.Provenance != ScenarioProvenance.Synthetic ||
            !candidate.ApprovedReadOnly ||
            candidate.CanonicalBytes is null ||
            candidate.CanonicalBytes.Length is < 1 or > 1_048_576 ||
            candidate.Sha256 is null ||
            candidate.Sha256.Length != 64)
        {
            throw new InvalidOperationException("Unverified laboratory scenario.");
        }

        byte[] expected;
        try { expected = Convert.FromHexString(candidate.Sha256); }
        catch (FormatException) { throw new InvalidOperationException("Invalid laboratory digest."); }

        // Clone before hashing: the catalog may retain and mutate its own byte buffer.
        byte[] canonical = candidate.CanonicalBytes.ToArray();
        byte[] actual = SHA256.HashData(canonical);
        if (!CryptographicOperations.FixedTimeEquals(actual, expected))
            throw new InvalidOperationException("Laboratory scenario digest mismatch.");

        return new ScenarioSnapshot(candidate.Id, candidate.Revision, canonical,
            Convert.ToHexString(actual).ToLowerInvariant());
    }
}

public interface IScenarioCatalog
{
    Task<ScenarioCandidate?> LoadAsync(string id, long revision, CancellationToken cancellationToken);
}

public interface IScenarioRuntime
{
    // Runtime is a test-only service; implementations must not re-enter the coordinator.
    Task PrepareAsync(ScenarioSnapshot snapshot, CancellationToken cancellationToken);
    Task StopAsync(CancellationToken cancellationToken);
}

public readonly record struct SessionToken(ulong Id, ulong Generation);
