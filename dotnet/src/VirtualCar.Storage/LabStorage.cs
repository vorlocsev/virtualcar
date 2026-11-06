using System.Security.Cryptography;
using System.Text;
using Microsoft.Data.Sqlite;

namespace VirtualCar.Storage;

public sealed record VehicleProfile(string Id, string Label, string Platform, int? ModelYear, string Provenance);
public sealed record SealedMetadata(string Id, string ScenarioId, int Revision, string Sha256, string VehicleProfileId)
{
    public bool SnapshotBytesVerified => false;
    public bool RuntimeSelected => false;
    public bool PhysicalVehicleVerified => false;
}
public sealed class LabStorageException(string message) : InvalidOperationException(message);

/// <summary>SQLite is control-plane only. CAN/ISO-TP frame handlers must never query it.</summary>
public sealed class LabStorage : IDisposable
{
    private const string SchemaName = "VirtualCar.Storage.Schema0001.sql";
    private readonly SqliteConnection _connection;
    private readonly SemaphoreSlim _mutex = new(1, 1);
    private bool _disposed;

    private LabStorage(SqliteConnection connection) => _connection = connection;

    public static LabStorage Open(string databasePath, bool initialize = false)
    {
        var path = SafePath(databasePath);
        bool created = false;
        SqliteConnection? conn = null;
        try
        {
            if (initialize)
            {
                using (new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None)) { }
                created = true;
            }
            else if (!File.Exists(path))
                throw new LabStorageException("Database not found.");
            if (new FileInfo(path).Length > 64 * 1024 * 1024)
                throw new LabStorageException("Database exceeds size limit.");

            var options = new SqliteConnectionStringBuilder {
                DataSource = path, Mode = SqliteOpenMode.ReadWrite,
                Pooling = false, ForeignKeys = true, DefaultTimeout = 5
            };
            conn = new SqliteConnection(options.ToString());
            conn.Open();
            Run(conn, "PRAGMA trusted_schema=OFF; PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000; PRAGMA journal_mode=WAL;");

            byte[] schema = Schema();
            string checksum = Convert.ToHexString(SHA256.HashData(schema)).ToLowerInvariant();
            if (initialize)
            {
                using var tx = conn.BeginTransaction();
                using (var ddl = conn.CreateCommand())
                {
                    ddl.Transaction = tx;
                    ddl.CommandText = Encoding.UTF8.GetString(schema);
                    ddl.ExecuteNonQuery();
                }
                using (var version = conn.CreateCommand())
                {
                    version.Transaction = tx;
                    version.CommandText = "INSERT INTO schema_migrations(version,checksum_sha256,applied_utc) VALUES(1,$sha,$now)";
                    version.Parameters.AddWithValue("$sha", checksum);
                    version.Parameters.AddWithValue("$now", DateTimeOffset.UtcNow.ToString("O"));
                    version.ExecuteNonQuery();
                }
                tx.Commit();
            }
            Verify(conn, checksum);
            return new LabStorage(conn);
        }
        catch
        {
            conn?.Dispose();
            if (created)
            {
                foreach (string suffix in new[] { "", "-wal", "-shm" })
                {
                    try { File.Delete(path + suffix); } catch (IOException) { }
                }
            }
            throw new LabStorageException("Lab SQLite open or migration verification failed.");
        }
    }

    public async Task AddSyntheticProfileAsync(string id, string label, string platform,
        int? year, CancellationToken ct = default)
    {
        if (!ValidId(id) || string.IsNullOrWhiteSpace(label) || label.Length > 96 ||
            string.IsNullOrWhiteSpace(platform) || platform.Length > 40 ||
            (year.HasValue && (year < 1900 || year > 2200)))
            throw new LabStorageException("Invalid synthetic metadata.");
        await _mutex.WaitAsync(ct).ConfigureAwait(false);
        try
        {
            RequireOpen();
            using var c = _connection.CreateCommand();
            c.CommandText = "INSERT INTO vehicle_profiles(id,label,platform,model_year,provenance,created_utc) VALUES($id,$label,$platform,$year,'synthetic',$now)";
            c.Parameters.AddWithValue("$id", id);
            c.Parameters.AddWithValue("$label", label);
            c.Parameters.AddWithValue("$platform", platform);
            c.Parameters.AddWithValue("$year", (object?)year ?? DBNull.Value);
            c.Parameters.AddWithValue("$now", DateTimeOffset.UtcNow.ToString("O"));
            await c.ExecuteNonQueryAsync(ct).ConfigureAwait(false);
        }
        finally { _mutex.Release(); }
    }

    public async Task<IReadOnlyList<VehicleProfile>> ListProfilesAsync(int limit = 100,
        CancellationToken ct = default)
    {
        if (limit is < 1 or > 100) throw new LabStorageException("Invalid result limit.");
        await _mutex.WaitAsync(ct).ConfigureAwait(false);
        try
        {
            RequireOpen();
            using var c = _connection.CreateCommand();
            c.CommandText = "SELECT id,label,platform,model_year,provenance FROM vehicle_profiles ORDER BY id LIMIT $limit";
            c.Parameters.AddWithValue("$limit", limit);
            await using var rows = await c.ExecuteReaderAsync(ct).ConfigureAwait(false);
            var result = new List<VehicleProfile>();
            while (await rows.ReadAsync(ct).ConfigureAwait(false))
                result.Add(new VehicleProfile(rows.GetString(0), rows.GetString(1), rows.GetString(2),
                    rows.IsDBNull(3) ? null : rows.GetInt32(3), rows.GetString(4)));
            return result;
        }
        finally { _mutex.Release(); }
    }

    public async Task<SealedMetadata?> ReadSealedMetadataAsync(string scenarioId, int revision,
        CancellationToken ct = default)
    {
        if (!ValidId(scenarioId) || revision < 1)
            throw new LabStorageException("Invalid scenario selector.");
        await _mutex.WaitAsync(ct).ConfigureAwait(false);
        try
        {
            RequireOpen();
            using var c = _connection.CreateCommand();
            c.CommandText = @"SELECT sr.id,sr.scenario_id,sr.revision,sr.snapshot_sha256,sc.vehicle_profile_id
                FROM scenario_revisions sr JOIN scenarios sc ON sc.id=sr.scenario_id
                WHERE sr.scenario_id=$id AND sr.revision=$revision AND sr.sealed=1";
            c.Parameters.AddWithValue("$id", scenarioId);
            c.Parameters.AddWithValue("$revision", revision);
            await using var reader = await c.ExecuteReaderAsync(ct).ConfigureAwait(false);
            if (!await reader.ReadAsync(ct).ConfigureAwait(false)) return null;
            var s = new SealedMetadata(reader.GetString(0), reader.GetString(1),
                reader.GetInt32(2), reader.GetString(3), reader.GetString(4));
            if (!ValidId(s.Id) || !ValidId(s.VehicleProfileId) ||
                s.Sha256.Length != 64 || !s.Sha256.All(Uri.IsHexDigit) ||
                await reader.ReadAsync(ct).ConfigureAwait(false))
                throw new LabStorageException("Malformed or ambiguous scenario metadata.");
            return s; // An SQL checksum is NOT approval to simulate an ECU!
        }
        finally { _mutex.Release(); }
    }

    public void BackupTo(string destinationPath)
    {
        var path = SafePath(destinationPath);
        _mutex.Wait();
        try
        {
            RequireOpen();
            using (new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None)) { }
            try
            {
                using var backup = new SqliteConnection(new SqliteConnectionStringBuilder {
                    DataSource = path, Mode = SqliteOpenMode.ReadWrite, Pooling = false
                }.ToString());
                backup.Open();
                _connection.BackupDatabase(backup);
            }
            catch
            {
                try { File.Delete(path); } catch (IOException) { }
                throw new LabStorageException("SQLite backup failed.");
            }
        }
        finally { _mutex.Release(); }
    }

    public void Dispose()
    {
        _mutex.Wait();
        try
        {
            if (_disposed) return;
            _disposed = true;
            _connection.Dispose();
        }
        finally { _mutex.Release(); }
    }

    private void RequireOpen()
    {
        if (_disposed) throw new ObjectDisposedException(nameof(LabStorage));
    }

    private static bool ValidId(string? s)
        => s is { Length: >= 1 and <= 96 } && s.All(c => char.IsAsciiLetterOrDigit(c) || c is '_' or '-');

    private static string SafePath(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || !Path.IsPathFullyQualified(path) ||
            !Path.GetExtension(path).Equals(".db", StringComparison.OrdinalIgnoreCase))
            throw new LabStorageException("Require a full local .db path.");
        string full = Path.GetFullPath(path);
        var parent = new DirectoryInfo(Path.GetDirectoryName(full)!);
        if (!parent.Exists || parent.LinkTarget is not null || new FileInfo(full).LinkTarget is not null)
            throw new LabStorageException("Symlink or absent database parent.");
        return full;
    }

    private static byte[] Schema()
    {
        using var stream = typeof(LabStorage).Assembly.GetManifestResourceStream(SchemaName)
            ?? throw new LabStorageException("Missing embedded v1 schema.");
        using var output = new MemoryStream();
        stream.CopyTo(output);
        if (output.Length is < 1 or > 131072)
            throw new LabStorageException("Invalid schema size.");
        return output.ToArray();
    }

    private static void Verify(SqliteConnection db, string checksum)
    {
        using (var integrity = db.CreateCommand())
        {
            integrity.CommandText = "PRAGMA quick_check";
            if ((string?)integrity.ExecuteScalar() != "ok")
                throw new LabStorageException("Integrity check failed.");
        }
        using (var foreignKeys = db.CreateCommand())
        {
            foreignKeys.CommandText = "PRAGMA foreign_keys";
            if (Convert.ToInt32(foreignKeys.ExecuteScalar()) != 1)
                throw new LabStorageException("Foreign key enforcement failed.");
        }
        using var c = db.CreateCommand();
        c.CommandText = "SELECT version,checksum_sha256 FROM schema_migrations";
        using var rows = c.ExecuteReader();
        if (!rows.Read() || rows.GetInt32(0) != 1 || rows.GetString(1) != checksum || rows.Read())
            throw new LabStorageException("Unexpected v1 migration checksum.");
    }

    private static void Run(SqliteConnection db, string sql)
    {
        using var c = db.CreateCommand();
        c.CommandText = sql;
        c.ExecuteNonQuery();
    }
}
