using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using Microsoft.Data.Sqlite;

namespace VirtualCar.Storage;

public sealed class LabStorageException(string message, Exception? inner = null) : Exception(message, inner);

public sealed record VehicleProfileMetadata(string Id, string Label, string Platform,
    long? ModelYear, string Provenance);

public sealed record ScenarioRevisionMetadata(string Id, string ScenarioId, long Revision,
    string SnapshotSha256, string VehicleProfileId, string Provenance)
{
    // Metadata is not a compiled scenario. Never enable ECU replies from it.
    public bool SnapshotBytesVerified => false;
    public bool RuntimeApproved => false;
}

public sealed record CatalogHealth(int SchemaVersion, long Profiles, long SealedRevisions,
    bool IntegrityOk, bool PhysicalAdapterVerified);

/// <summary>
/// Local per-user SQLite control-plane catalog. It deliberately exposes ONLY
/// metadata and cannot serve J2534 frames, private traces, VIN or PIN.
/// </summary>
public sealed partial class LabCatalog : IAsyncDisposable
{
    private const int Version = 1;
    private const long MaxDatabaseBytes = 64L * 1024 * 1024;
    private static readonly Regex IdPattern = new("^[A-Za-z0-9_-]{1,96}$",
        RegexOptions.Compiled | RegexOptions.CultureInvariant,
        TimeSpan.FromMilliseconds(100));

    private readonly SqliteConnection _connection;
    private readonly SemaphoreSlim _mutex = new(1, 1);
    private readonly string _schemaSha256;
    private bool _disposed;

    private LabCatalog(SqliteConnection connection, string digest)
    {
        _connection = connection;
        _schemaSha256 = digest;
    }

    public static async Task<LabCatalog> CreateAsync(string databasePath,
        CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        string path = ValidatePath(databasePath, create: true);
        bool ownFile = false;
        SqliteConnection? connection = null;
        try
        {
            using (new FileStream(path, FileMode.CreateNew, FileAccess.Write,
                       FileShare.None, 1, FileOptions.WriteThrough))
                ownFile = true;

            connection = await ConnectAsync(path, cancellationToken).ConfigureAwait(false);
            (string sql, string digest) = LoadCanonicalSchema();
            using (var transaction = connection.BeginTransaction())
            {
                using var ddl = connection.CreateCommand();
                ddl.Transaction = transaction;
                ddl.CommandText = sql;
                await ddl.ExecuteNonQueryAsync(cancellationToken).ConfigureAwait(false);

                using var journal = connection.CreateCommand();
                journal.Transaction = transaction;
                journal.CommandText = """
                    INSERT INTO schema_migrations(version,checksum_sha256,applied_utc)
                    VALUES(1,$digest,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
                    """;
                journal.Parameters.AddWithValue("$digest", digest);
                await journal.ExecuteNonQueryAsync(cancellationToken).ConfigureAwait(false);
                transaction.Commit();
            }
            var result = new LabCatalog(connection, digest);
            await result.VerifyAsync(cancellationToken).ConfigureAwait(false);
            ownFile = false;
            return result;
        }
        catch (Exception e) when (e is SqliteException or IOException or UnauthorizedAccessException
                                  or LabStorageException or OperationCanceledException)
        {
            if (connection is not null) await connection.DisposeAsync().ConfigureAwait(false);
            if (ownFile) RemoveUnfinishedNewDatabase(path);
            if (e is OperationCanceledException) throw;
            throw new LabStorageException("Local SQLite catalog initialization failed.", e);
        }
    }

    public static async Task<LabCatalog> OpenAsync(string databasePath,
        CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        string path = ValidatePath(databasePath, create: false);
        SqliteConnection? connection = null;
        try
        {
            connection = await ConnectAsync(path, cancellationToken).ConfigureAwait(false);
            (_, string digest) = LoadCanonicalSchema();
            var catalog = new LabCatalog(connection, digest);
            await catalog.VerifyAsync(cancellationToken).ConfigureAwait(false);
            return catalog;
        }
        catch (Exception e) when (e is SqliteException or IOException or UnauthorizedAccessException
                                  or LabStorageException or OperationCanceledException)
        {
            if (connection is not null) await connection.DisposeAsync().ConfigureAwait(false);
            if (e is OperationCanceledException) throw;
            throw new LabStorageException("Local SQLite catalog verification failed.", e);
        }
    }

    public async Task<IReadOnlyList<VehicleProfileMetadata>> ListProfilesAsync(int limit = 100,
        CancellationToken cancellationToken = default)
    {
        if (limit is < 1 or > 100) throw new ArgumentOutOfRangeException(nameof(limit));
        await _mutex.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            EnsureOpen();
            using var command = _connection.CreateCommand();
            command.CommandText = """
                SELECT id,label,platform,model_year,provenance
                FROM vehicle_profiles ORDER BY id LIMIT $limit;
                """;
            command.Parameters.AddWithValue("$limit", limit);
            using var reader = await command.ExecuteReaderAsync(cancellationToken).ConfigureAwait(false);
            var profiles = new List<VehicleProfileMetadata>();
            while (await reader.ReadAsync(cancellationToken).ConfigureAwait(false))
            {
                string id = reader.GetString(0);
                if (!IdPattern.IsMatch(id)) throw new LabStorageException("Invalid profile identifier.");
                profiles.Add(new VehicleProfileMetadata(id, reader.GetString(1), reader.GetString(2),
                    reader.IsDBNull(3) ? null : reader.GetInt64(3), reader.GetString(4)));
            }
            return profiles;
        }
        finally { _mutex.Release(); }
    }

    public async Task<ScenarioRevisionMetadata?> GetSealedRevisionAsync(string scenarioId,
        long revision, CancellationToken cancellationToken = default)
    {
        if (!IdPattern.IsMatch(scenarioId) || revision is < 1 or > int.MaxValue)
            throw new ArgumentException("Invalid scenario selector.", nameof(scenarioId));

        await _mutex.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            EnsureOpen();
            using var command = _connection.CreateCommand();
            command.CommandText = """
                SELECT sr.id,sr.scenario_id,sr.revision,sr.snapshot_sha256,
                       s.vehicle_profile_id,v.provenance
                FROM scenario_revisions sr
                JOIN scenarios s ON s.id=sr.scenario_id
                JOIN vehicle_profiles v ON v.id=s.vehicle_profile_id
                WHERE sr.scenario_id=$id AND sr.revision=$rev AND sr.sealed=1;
                """;
            command.Parameters.AddWithValue("$id", scenarioId);
            command.Parameters.AddWithValue("$rev", revision);
            using var reader = await command.ExecuteReaderAsync(cancellationToken).ConfigureAwait(false);
            if (!await reader.ReadAsync(cancellationToken).ConfigureAwait(false))
                return null;
            string digest = reader.GetString(3);
            if (digest.Length != 64 || !digest.All(Uri.IsHexDigit))
                throw new LabStorageException("Invalid scenario metadata digest.");
            return new ScenarioRevisionMetadata(
                reader.GetString(0), reader.GetString(1), reader.GetInt64(2), digest.ToLowerInvariant(),
                reader.GetString(4), reader.GetString(5));
        }
        finally { _mutex.Release(); }
    }

    public async Task<CatalogHealth> GetHealthAsync(CancellationToken cancellationToken = default)
    {
        await _mutex.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            EnsureOpen();
            await VerifyAsync(cancellationToken).ConfigureAwait(false);
            return new CatalogHealth(Version,
                await ScalarCountAsync("SELECT count(*) FROM vehicle_profiles;", cancellationToken)
                    .ConfigureAwait(false),
                await ScalarCountAsync("SELECT count(*) FROM scenario_revisions WHERE sealed=1;",
                    cancellationToken).ConfigureAwait(false),
                IntegrityOk: true, PhysicalAdapterVerified: false);
        }
        finally { _mutex.Release(); }
    }

    /// <summary>SQLite online backup, not an unsafe copy of a WAL database file.</summary>
    public async Task BackupAsync(string targetPath, CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        string destination = ValidatePath(targetPath, create: true);
        await _mutex.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            EnsureOpen();
            if (Path.GetFullPath(_connection.DataSource).Equals(destination,
                    OperatingSystem.IsWindows() ? StringComparison.OrdinalIgnoreCase : StringComparison.Ordinal))
                throw new LabStorageException("Backup destination matches the source.");

            bool reserved = false;
            try
            {
                using (new FileStream(destination, FileMode.CreateNew, FileAccess.Write,
                           FileShare.None, 1, FileOptions.WriteThrough))
                    reserved = true;
                await using var backup = await ConnectAsync(destination, cancellationToken)
                    .ConfigureAwait(false);
                _connection.BackupDatabase(backup);
                using var check = backup.CreateCommand();
                check.CommandText = "PRAGMA quick_check;";
                var status = (string?)await check.ExecuteScalarAsync(cancellationToken).ConfigureAwait(false);
                if (status != "ok") throw new LabStorageException("SQLite backup integrity check failed.");
                cancellationToken.ThrowIfCancellationRequested();
                reserved = false;
            }
            finally
            {
                if (reserved) RemoveUnfinishedNewDatabase(destination);
            }
        }
        finally { _mutex.Release(); }
    }

    private async Task<long> ScalarCountAsync(string sql, CancellationToken ct)
    {
        using var command = _connection.CreateCommand();
        command.CommandText = sql;
        return Convert.ToInt64(await command.ExecuteScalarAsync(ct).ConfigureAwait(false));
    }

    private async Task VerifyAsync(CancellationToken ct)
    {
        using (var check = _connection.CreateCommand())
        {
            check.CommandText = "PRAGMA quick_check;";
            if ((string?)await check.ExecuteScalarAsync(ct).ConfigureAwait(false) != "ok")
                throw new LabStorageException("SQLite quick_check failed.");
        }

        using (var fk = _connection.CreateCommand())
        {
            fk.CommandText = "PRAGMA foreign_keys;";
            if (Convert.ToInt64(await fk.ExecuteScalarAsync(ct).ConfigureAwait(false)) != 1L)
                throw new LabStorageException("SQLite foreign keys disabled.");
        }

        using (var violations = _connection.CreateCommand())
        {
            violations.CommandText = "PRAGMA foreign_key_check;";
            using var reader = await violations.ExecuteReaderAsync(ct).ConfigureAwait(false);
            if (await reader.ReadAsync(ct).ConfigureAwait(false))
                throw new LabStorageException("SQLite foreign-key integrity failed.");
        }

        using (var migration = _connection.CreateCommand())
        {
            migration.CommandText = "SELECT version,checksum_sha256 FROM schema_migrations ORDER BY version;";
            using var reader = await migration.ExecuteReaderAsync(ct).ConfigureAwait(false);
            if (!await reader.ReadAsync(ct).ConfigureAwait(false) ||
                reader.GetInt64(0) != Version ||
                reader.GetString(1) != _schemaSha256 ||
                await reader.ReadAsync(ct).ConfigureAwait(false))
                throw new LabStorageException("Unexpected SQLite schema migration.");
        }
    }

    private static async Task<SqliteConnection> ConnectAsync(string path, CancellationToken ct)
    {
        var builder = new SqliteConnectionStringBuilder
        {
            DataSource = path,
            Mode = SqliteOpenMode.ReadWrite,
            Cache = SqliteCacheMode.Private,
            Pooling = false,
            DefaultTimeout = 5
        };
        var connection = new SqliteConnection(builder.ToString());
        try
        {
            await connection.OpenAsync(ct).ConfigureAwait(false);
            foreach (string commandText in new[]
            {
                "PRAGMA trusted_schema=OFF;",
                "PRAGMA foreign_keys=ON;",
                "PRAGMA busy_timeout=5000;",
                "PRAGMA journal_mode=WAL;",
                "PRAGMA synchronous=FULL;"
            })
            {
                using var cmd = connection.CreateCommand();
                cmd.CommandText = commandText;
                await cmd.ExecuteNonQueryAsync(ct).ConfigureAwait(false);
            }
            return connection;
        }
        catch
        {
            await connection.DisposeAsync().ConfigureAwait(false);
            throw;
        }
    }

    private static (string Sql, string Hash) LoadCanonicalSchema()
    {
        using var stream = typeof(LabCatalog).Assembly.GetManifestResourceStream(
            "VirtualCar.Storage.schema.v1.sql") ??
            throw new LabStorageException("Canonical schema resource not available.");
        using var memory = new MemoryStream();
        stream.CopyTo(memory);
        byte[] content = memory.ToArray();
        if (content.Length is < 1 or > 262_144)
            throw new LabStorageException("Invalid schema resource length.");
        return (Encoding.UTF8.GetString(content), Convert.ToHexString(SHA256.HashData(content)).ToLowerInvariant());
    }

    private static string ValidatePath(string value, bool create)
    {
        if (string.IsNullOrWhiteSpace(value) || value.Contains('\0') ||
            value.Contains('?') || value.Contains('#') ||
            !string.Equals(Path.GetExtension(value), ".db", StringComparison.OrdinalIgnoreCase))
            throw new LabStorageException("Invalid local database path.");
        string full = Path.GetFullPath(value);
        string parent = Path.GetDirectoryName(full) ??
            throw new LabStorageException("Missing database parent directory.");
        if (!Directory.Exists(parent) ||
            (File.GetAttributes(parent) & FileAttributes.ReparsePoint) != 0)
            throw new LabStorageException("Unsafe database parent directory.");
        if (create)
        {
            if (File.Exists(full)) throw new LabStorageException("Database already exists.");
        }
        else
        {
            if (!File.Exists(full) ||
                (File.GetAttributes(full) & FileAttributes.ReparsePoint) != 0 ||
                new FileInfo(full).Length > MaxDatabaseBytes)
                throw new LabStorageException("Existing local database unavailable.");
        }
        return full;
    }

    private static void RemoveUnfinishedNewDatabase(string path)
    {
        foreach (string file in new[] { path, path + "-wal", path + "-shm" })
        {
            try { if (File.Exists(file)) File.Delete(file); }
            catch (IOException) { /* No unverified partial DB may be reopened automatically. */ }
            catch (UnauthorizedAccessException) { }
        }
    }

    private void EnsureOpen()
    {
        if (_disposed) throw new ObjectDisposedException(nameof(LabCatalog));
    }

    public async ValueTask DisposeAsync()
    {
        await _mutex.WaitAsync().ConfigureAwait(false);
        try
        {
            if (_disposed) return;
            _disposed = true;
            await _connection.DisposeAsync().ConfigureAwait(false);
        }
        finally { _mutex.Release(); }
    }
}
