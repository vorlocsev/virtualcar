using Microsoft.Data.Sqlite;

namespace VirtualCar.Storage;

// Materialization boundary: these types are for the trusted local scenario
// compiler only. Do NOT serialize them into GUI results, CI logs, or IPC.
public sealed record ScenarioMaterial(
    string ScenarioId, string ScenarioLabel, long Revision, bool Sealed,
    string? ExpectedSha256, string VehicleId, string VehiclePlatform,
    long? VehicleModelYear, string VehicleProvenance,
    IReadOnlyList<ScenarioFixtureMaterial> Fixtures);

public sealed record ScenarioFixtureMaterial(
    string BusId, long Bitrate, string IdFormat,
    string EcuId, string Transport, long RequestCanId, long ResponseCanId,
    bool EcuEnabled, string FixtureId, string RequestSha256,
    string FixtureProvenance, string LabApproval, byte[]? SyntheticReply);

public sealed partial class LabCatalog
{
    /// <summary>
    /// Reads a coherent scenario/ECU/binding snapshot from the original
    /// SQLite v1 schema. Does not authorize or execute any diagnostic reply.
    /// Only the caller's separately approved synthetic request manifest can
    /// supply the missing original request bytes for SHA verification.
    /// </summary>
    public async Task<ScenarioMaterial?> ReadScenarioMaterialAsync(
        string scenarioId, long revision, CancellationToken cancellationToken = default)
    {
        if (scenarioId is null || !IdPattern.IsMatch(scenarioId) ||
            revision is < 1 or > int.MaxValue)
            throw new ArgumentException("Invalid scenario selector.", nameof(scenarioId));

        await _mutex.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            EnsureOpen();
            using var tx = _connection.BeginTransaction();
            string revisionId;
            string label;
            bool sealedRevision;
            string? digest;
            string vehicleId;
            string platform;
            long? modelYear;
            string provenance;

            using (var select = _connection.CreateCommand())
            {
                select.Transaction = tx;
                select.CommandText = """
                    SELECT sr.id,s.label,sr.sealed,sr.snapshot_sha256,
                           v.id,v.platform,v.model_year,v.provenance
                    FROM scenario_revisions sr
                    JOIN scenarios s ON s.id=sr.scenario_id
                    JOIN vehicle_profiles v ON v.id=s.vehicle_profile_id
                    WHERE sr.scenario_id=$scenario AND sr.revision=$revision;
                    """;
                select.Parameters.AddWithValue("$scenario", scenarioId);
                select.Parameters.AddWithValue("$revision", revision);
                using var reader = await select.ExecuteReaderAsync(cancellationToken).ConfigureAwait(false);
                if (!await reader.ReadAsync(cancellationToken).ConfigureAwait(false))
                    return null;

                revisionId = reader.GetString(0);
                label = reader.GetString(1);
                sealedRevision = reader.GetInt64(2) == 1;
                digest = reader.IsDBNull(3) ? null : reader.GetString(3);
                vehicleId = reader.GetString(4);
                platform = reader.GetString(5);
                modelYear = reader.IsDBNull(6) ? null : reader.GetInt64(6);
                provenance = reader.GetString(7);
            }

            var fixtures = new List<ScenarioFixtureMaterial>();
            using (var select = _connection.CreateCommand())
            {
                select.Transaction = tx;
                select.CommandText = """
                    SELECT bus.id,bus.bitrate,bus.id_format,
                           ecu.id,ecu.transport,ecu.request_can_id,
                           ecu.response_can_id,ecu.enabled,
                           fixture.id,fixture.request_sha256,
                           fixture.provenance,fixture.lab_approval,
                           fixture.synthetic_reply,bus.vehicle_profile_id
                    FROM scenario_bindings binding
                    JOIN response_fixtures fixture ON fixture.id=binding.fixture_id
                    JOIN ecu_nodes ecu ON ecu.id=fixture.ecu_id
                    JOIN can_buses bus ON bus.id=ecu.bus_id
                    WHERE binding.revision_id=$revisionId AND binding.enabled=1
                    ORDER BY bus.id,ecu.id,fixture.id;
                    """;
                select.Parameters.AddWithValue("$revisionId", revisionId);
                using var reader = await select.ExecuteReaderAsync(cancellationToken).ConfigureAwait(false);
                while (await reader.ReadAsync(cancellationToken).ConfigureAwait(false))
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    if (fixtures.Count >= 256)
                        throw new LabStorageException("Too many scenario response bindings.");
                    if (!string.Equals(reader.GetString(13), vehicleId, StringComparison.Ordinal))
                        throw new LabStorageException("Cross-vehicle ECU binding rejected.");

                    // Captured bytes must remain in encrypted private artifacts.
                    // Never return a private artifact through this metadata API.
                    byte[]? syntheticReply = reader.IsDBNull(12)
                        ? null
                        : reader.GetFieldValue<byte[]>(12).ToArray();

                    fixtures.Add(new ScenarioFixtureMaterial(
                        reader.GetString(0),
                        reader.GetInt64(1),
                        reader.GetString(2),
                        reader.GetString(3),
                        reader.GetString(4),
                        reader.GetInt64(5),
                        reader.GetInt64(6),
                        reader.GetInt64(7) == 1,
                        reader.GetString(8),
                        reader.GetString(9),
                        reader.GetString(10),
                        reader.GetString(11),
                        syntheticReply));
                }
            }
            tx.Commit();
            return new ScenarioMaterial(scenarioId, label, revision,
                sealedRevision, digest, vehicleId, platform, modelYear,
                provenance, fixtures.ToArray());
        }
        finally { _mutex.Release(); }
    }
}
