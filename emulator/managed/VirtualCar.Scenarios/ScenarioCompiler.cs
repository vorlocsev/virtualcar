using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using VirtualCar.Core;
using VirtualCar.Storage;

namespace VirtualCar.Scenarios;

public sealed class ScenarioCompilationException(string reason)
    : Exception(reason);

/// <summary>
/// SQLite v1 contains only request_sha256, not request bytes. A separate,
/// explicitly synthetic request manifest must supply those bytes. No request
/// can be inferred from a digest or an assumed Volvo protocol response.
/// </summary>
public interface ISyntheticRequestManifest
{
    Task<byte[]?> ResolveAsync(string requestSha256, CancellationToken cancellationToken);
}

/// <summary>
/// Metadata-only preview. In particular it cannot enable an ECU response.
/// </summary>
public sealed record ScenarioPreview(string Sha256, int ResponseCount, bool RuntimeApproved)
{
    public bool SnapshotBytesVerified => false;
}

/// <summary>
/// Compiles only generic synthetic UDS ReadDataByIdentifier scenarios.
/// D2, CEM, security access, programming and private captured fixtures
/// are deliberately unsupported at migration M2.
/// </summary>
public sealed class ScenarioCompiler(LabCatalog catalog, ISyntheticRequestManifest requests)
{
    private const int MaxFixtures = 128;
    private const int MaxSnapshotBytes = 1024 * 1024;
    private static readonly Regex IdPattern = new("^[A-Za-z0-9_-]{1,96}$",
        RegexOptions.Compiled | RegexOptions.CultureInvariant,
        TimeSpan.FromMilliseconds(100));

    public async Task<ScenarioPreview> PreviewDraftAsync(
        string scenarioId, long revision, CancellationToken cancellationToken = default)
    {
        ScenarioMaterial source = await ReadAsync(scenarioId, revision, cancellationToken)
            .ConfigureAwait(false);
        if (source.Sealed || source.ExpectedSha256 is not null)
            throw new ScenarioCompilationException("Only unsealed draft scenarios can be previewed.");
        (byte[] _, string hash) = await MaterializeAsync(source, cancellationToken)
            .ConfigureAwait(false);
        return new ScenarioPreview(hash, source.Fixtures.Count, RuntimeApproved: false);
    }

    public async Task<ScenarioCandidate> CompileVerifiedAsync(
        string scenarioId, long revision, CancellationToken cancellationToken = default)
    {
        ScenarioMaterial source = await ReadAsync(scenarioId, revision, cancellationToken)
            .ConfigureAwait(false);
        if (!source.Sealed || string.IsNullOrWhiteSpace(source.ExpectedSha256))
            throw new ScenarioCompilationException("Scenario revision has not been sealed.");
        (byte[] materialized, string computed) = await MaterializeAsync(source, cancellationToken)
            .ConfigureAwait(false);
        byte[] storedHash;
        try { storedHash = Convert.FromHexString(source.ExpectedSha256); }
        catch (FormatException)
        {
            throw new ScenarioCompilationException("Malformed stored scenario checksum.");
        }
        if (storedHash.Length != 32 ||
            !CryptographicOperations.FixedTimeEquals(storedHash, SHA256.HashData(materialized)))
            throw new ScenarioCompilationException("Materialized scenario SHA-256 mismatch.");
        if (!string.Equals(computed, Convert.ToHexString(storedHash).ToLowerInvariant(),
                StringComparison.Ordinal))
            throw new ScenarioCompilationException("Scenario checksum normalization mismatch.");

        // The coordinator separately verifies SHA-256 on an independent copy
        // of these exact canonical bytes before any runtime preparation.
        return new ScenarioCandidate(source.ScenarioId, source.Revision,
            ScenarioProvenance.Synthetic, ApprovedReadOnly: true,
            materialized, computed);
    }

    private async Task<ScenarioMaterial> ReadAsync(
        string id, long revision, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(id) || !IdPattern.IsMatch(id) ||
            revision is < 1 or > int.MaxValue)
            throw new ScenarioCompilationException("Invalid scenario selector.");
        ScenarioMaterial? material = await catalog.ReadScenarioMaterialAsync(
            id, revision, cancellationToken).ConfigureAwait(false);
        return material ?? throw new ScenarioCompilationException("Scenario revision not found.");
    }

    private async Task<(byte[] Data, string Hash)> MaterializeAsync(
        ScenarioMaterial source, CancellationToken cancellationToken)
    {
        if (!ValidId(source.ScenarioId) || !ValidId(source.VehicleId) ||
            source.ScenarioLabel.Length is < 1 or > 96 ||
            source.VehiclePlatform.Length is < 1 or > 40 ||
            source.VehicleProvenance != "synthetic" ||
            source.Revision is < 1 or > int.MaxValue ||
            source.Fixtures.Count is < 1 or > MaxFixtures ||
            (source.VehicleModelYear is not null &&
                source.VehicleModelYear is < 1900 or > 2200))
            throw new ScenarioCompilationException("Unapproved or invalid laboratory vehicle.");

        var seenRequests = new HashSet<(string Bus, string Ecu, string Hash)>();
        var buses = new Dictionary<string, (long Rate, string Format)>(StringComparer.Ordinal);
        var ecus = new Dictionary<(string Bus, string Ecu), (long Req, long Resp, string Transport)>();
        var reqOwners = new Dictionary<(string Bus, long CanId), string>();
        var respOwners = new Dictionary<(string Bus, long CanId), string>();
        var compiled = new List<(ScenarioFixtureMaterial Fixture, byte[] Request, byte[] Reply)>();

        foreach (ScenarioFixtureMaterial item in source.Fixtures
                     .OrderBy(x => x.BusId, StringComparer.Ordinal)
                     .ThenBy(x => x.EcuId, StringComparer.Ordinal)
                     .ThenBy(x => x.FixtureId, StringComparer.Ordinal))
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (!ValidId(item.BusId) || !ValidId(item.EcuId) || !ValidId(item.FixtureId) ||
                !item.EcuEnabled || item.FixtureProvenance != "synthetic" ||
                item.LabApproval != "approved_for_readonly_lab" ||
                item.Transport != "iso15765" ||
                item.Bitrate is not (125000 or 250000 or 500000 or 1000000) ||
                item.IdFormat is not ("11bit" or "29bit") ||
                item.SyntheticReply is null ||
                item.SyntheticReply.Length is < 3 or > 4095 ||
                item.RequestSha256.Length != 64 ||
                !item.RequestSha256.All(Uri.IsHexDigit))
                throw new ScenarioCompilationException("Unsupported or unapproved ECU fixture.");

            long maxCanId = item.IdFormat == "11bit" ? 0x7ff : 0x1fffffff;
            if (item.RequestCanId < 0 || item.ResponseCanId < 0 ||
                item.RequestCanId > maxCanId || item.ResponseCanId > maxCanId ||
                item.RequestCanId == item.ResponseCanId)
                throw new ScenarioCompilationException("Invalid CAN route.");

            if (buses.TryGetValue(item.BusId, out var bus) &&
                (bus.Rate != item.Bitrate || bus.Format != item.IdFormat))
                throw new ScenarioCompilationException("Inconsistent CAN bus settings.");
            buses[item.BusId] = (item.Bitrate, item.IdFormat);

            var ecuKey = (item.BusId, item.EcuId);
            if (ecus.TryGetValue(ecuKey, out var ecu) &&
                (ecu.Req != item.RequestCanId || ecu.Resp != item.ResponseCanId ||
                 ecu.Transport != item.Transport))
                throw new ScenarioCompilationException("Inconsistent ECU route.");
            ecus[ecuKey] = (item.RequestCanId, item.ResponseCanId, item.Transport);

            ValidateUniqueOwner(reqOwners, (item.BusId, item.RequestCanId), item.EcuId);
            ValidateUniqueOwner(respOwners, (item.BusId, item.ResponseCanId), item.EcuId);
            // Reject RX/TX collisions between different ECUs on the same bus.
            if (reqOwners.TryGetValue((item.BusId, item.ResponseCanId), out string? reqOwner) &&
                reqOwner != item.EcuId)
                throw new ScenarioCompilationException("Conflicting CAN request/response routes.");
            if (respOwners.TryGetValue((item.BusId, item.RequestCanId), out string? respOwner) &&
                respOwner != item.EcuId)
                throw new ScenarioCompilationException("Conflicting CAN request/response routes.");

            string requestHash = item.RequestSha256.ToLowerInvariant();
            if (!seenRequests.Add((item.BusId, item.EcuId, requestHash)))
                throw new ScenarioCompilationException("Ambiguous duplicate ECU response.");

            byte[]? provided = await requests.ResolveAsync(requestHash, cancellationToken)
                .ConfigureAwait(false);
            cancellationToken.ThrowIfCancellationRequested();
            if (provided is null || provided.Length != 3)
                throw new ScenarioCompilationException("Approved synthetic request bytes missing.");
            byte[] request = provided.ToArray();
            string digest = Convert.ToHexString(SHA256.HashData(request)).ToLowerInvariant();
            if (!string.Equals(digest, requestHash, StringComparison.Ordinal))
                throw new ScenarioCompilationException("Request byte hash mismatch.");

            byte[] reply = item.SyntheticReply.ToArray();
            // Only read-only UDS 0x22 and matching positive 0x62 are supported
            // here. In particular no 0x27 SecurityAccess or 0x2E writes.
            if (request[0] != 0x22 || reply[0] != 0x62 ||
                request[1] != reply[1] || request[2] != reply[2])
                throw new ScenarioCompilationException("Unsupported diagnostic service/reply.");
            compiled.Add((item, request, reply));
        }

        // Fully explicit binary LE v1 encoding, not JSON/property-order based.
        using var stream = new MemoryStream();
        using (var writer = new BinaryWriter(stream, new UTF8Encoding(false, true), leaveOpen: true))
        {
            writer.Write(new byte[] { (byte)'V', (byte)'C', (byte)'S', (byte)'N',
                (byte)'A', (byte)'P', (byte)'1', 0 });
            WriteString(writer, source.ScenarioId);
            WriteString(writer, source.ScenarioLabel);
            writer.Write(source.Revision);
            WriteString(writer, source.VehicleId);
            WriteString(writer, source.VehiclePlatform);
            writer.Write((int)(source.VehicleModelYear ?? -1));
            WriteString(writer, source.VehicleProvenance);
            writer.Write(compiled.Count);
            foreach (var (item, request, reply) in compiled)
            {
                WriteString(writer, item.BusId);
                writer.Write((int)item.Bitrate);
                WriteString(writer, item.IdFormat);
                WriteString(writer, item.EcuId);
                WriteString(writer, item.Transport);
                writer.Write((uint)item.RequestCanId);
                writer.Write((uint)item.ResponseCanId);
                WriteString(writer, item.FixtureId);
                WriteString(writer, item.FixtureProvenance);
                WriteString(writer, item.RequestSha256.ToLowerInvariant());
                writer.Write(request.Length);
                writer.Write(request);
                writer.Write(reply.Length);
                writer.Write(reply);
            }
        }
        if (stream.Length is < 1 or > MaxSnapshotBytes)
            throw new ScenarioCompilationException("Materialized scenario exceeds limits.");
        byte[] data = stream.ToArray();
        return (data, Convert.ToHexString(SHA256.HashData(data)).ToLowerInvariant());
    }

    private static void ValidateUniqueOwner(
        Dictionary<(string Bus, long CanId), string> owners,
        (string Bus, long CanId) key, string ecu)
    {
        if (owners.TryGetValue(key, out string? existing) && existing != ecu)
            throw new ScenarioCompilationException("Ambiguous ECU CAN identifiers.");
        owners[key] = ecu;
    }

    private static bool ValidId(string s) => s is not null && IdPattern.IsMatch(s);

    private static void WriteString(BinaryWriter writer, string text)
    {
        byte[] utf8 = new UTF8Encoding(false, true).GetBytes(text);
        if (utf8.Length > 512) throw new ScenarioCompilationException("String length exceeds limits.");
        writer.Write((ushort)utf8.Length);
        writer.Write(utf8);
    }
}

/// <summary>
/// Only a fully compiled and stored-SHA-verified scenario can be supplied to
/// the existing C# lifecycle coordinator. No automatic runtime is installed.
/// </summary>
public sealed class VerifiedScenarioCatalog(ScenarioCompiler compiler) : IScenarioCatalog
{
    public Task<ScenarioCandidate?> LoadAsync(
        string id, long revision, CancellationToken cancellationToken)
        => LoadVerifiedAsync(id, revision, cancellationToken);

    private async Task<ScenarioCandidate?> LoadVerifiedAsync(
        string id, long revision, CancellationToken cancellationToken)
        => await compiler.CompileVerifiedAsync(id, revision, cancellationToken)
            .ConfigureAwait(false);
}
