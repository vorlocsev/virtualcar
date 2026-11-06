using System.Security.Cryptography;
using Microsoft.Data.Sqlite;
using VirtualCar.Storage;

namespace VirtualCar.Storage.Checks;

internal static class Program
{
    private static async Task<int> Main()
    {
        (string Name, Func<Task> Test)[] tests =
        [
            ("01 Explicit SQLite create and reopen", Test01),
            ("02 Missing DB and overwrite are rejected", Test02),
            ("03 Changed or unknown migration rejected", Test03),
            ("04 Metadata-only profile listing", Test04),
            ("05 Sealed metadata never activates responses", Test05),
            ("06 WAL-compatible consistent backup", Test06),
            ("07 Corruption, bad selectors and bounds", Test07),
            ("08 Cancellation, concurrency, disposal", Test08),
            ("09 10 GiB target and 12 GiB size guard boundaries", Test09)
        ];
        int passed = 0;
        foreach ((string name, Func<Task> test) in tests)
        {
            try
            {
                await test();
                Console.WriteLine("PASS " + name);
                passed++;
            }
            catch (Exception e)
            {
                // Do not print local file paths, SQL payloads or private identifiers.
                Console.Error.WriteLine("FAIL " + name + " (" + e.GetType().Name + ")");
            }
        }
        Console.WriteLine($"VirtualCar.Storage SQLite gates: {passed}/{tests.Length}");
        return passed == tests.Length ? 0 : 1;
    }

    private sealed class Folder : IDisposable
    {
        public string PathValue { get; } = Path.Combine(Path.GetTempPath(), "virtualcar-lab-" + Guid.NewGuid().ToString("N"));

        public Folder() => Directory.CreateDirectory(PathValue);
        public string Db => Path.Combine(PathValue, "catalog.db");
        public string Backup => Path.Combine(PathValue, "backup.db");

        public void Dispose()
        {
            try { Directory.Delete(PathValue, true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    private static void Require(bool condition, string reason)
    {
        if (!condition) throw new InvalidOperationException(reason);
    }

    private static async Task Fail<T>(Func<Task> action) where T : Exception
    {
        try { await action(); }
        catch (T) { return; }
        throw new InvalidOperationException("Expected " + typeof(T).Name);
    }

    private static async Task InsertSyntheticAsync(string path)
    {
        await using var db = new SqliteConnection(new SqliteConnectionStringBuilder
        {
            DataSource = path, Mode = SqliteOpenMode.ReadWrite, Pooling = false
        }.ToString());
        await db.OpenAsync();
        using var command = db.CreateCommand();
        command.CommandText = """
            INSERT INTO vehicle_profiles(id,label,platform,model_year,provenance,created_utc)
            VALUES ('synthetic', 'Laboratory vehicle', 'GENERIC', 2009, 'synthetic', '2026-11-06T00:00:00Z');
            INSERT INTO scenarios(id,label,vehicle_profile_id,created_utc)
            VALUES ('scenario', 'Lab', 'synthetic', '2026-11-06T00:00:00Z');
            INSERT INTO scenario_revisions(id,scenario_id,revision,sealed,snapshot_sha256,created_utc)
            VALUES ('rev1','scenario',1,1,'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                    '2026-11-06T00:00:00Z');
            """;
        await command.ExecuteNonQueryAsync();
    }

    private static async Task Test01()
    {
        using var folder = new Folder();
        await using (var store = await LabCatalog.CreateAsync(folder.Db))
        {
            CatalogHealth health = await store.GetHealthAsync();
            Require(health.SchemaVersion == 1 && health.IntegrityOk && health.Profiles == 0,
                "Unexpected initial metadata");
            Require(!health.PhysicalAdapterVerified, "Metadata must not attest hardware");
        }
        await using var reopened = await LabCatalog.OpenAsync(folder.Db);
        Require((await reopened.GetHealthAsync()).SchemaVersion == 1, "Reopen failed");
    }

    private static async Task Test02()
    {
        using var folder = new Folder();
        await Fail<LabStorageException>(async () => { await using var _ = await LabCatalog.OpenAsync(folder.Db); });
        await using (var created = await LabCatalog.CreateAsync(folder.Db)) { }
        byte[] previous = await File.ReadAllBytesAsync(folder.Db);
        await Fail<LabStorageException>(async () => { await using var _ = await LabCatalog.CreateAsync(folder.Db); });
        byte[] after = await File.ReadAllBytesAsync(folder.Db);
        Require(previous.AsSpan().SequenceEqual(after), "Existing DB was overwritten");
    }

    private static async Task Test03()
    {
        using var folder = new Folder();
        await using (var store = await LabCatalog.CreateAsync(folder.Db)) { }
        await using (var direct = new SqliteConnection($"Data Source={folder.Db}"))
        {
            await direct.OpenAsync();
            using var edit = direct.CreateCommand();
            edit.CommandText = "UPDATE schema_migrations SET checksum_sha256='ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff';";
            await edit.ExecuteNonQueryAsync();
        }
        await Fail<LabStorageException>(async () => { await using var _ = await LabCatalog.OpenAsync(folder.Db); });
    }

    private static async Task Test04()
    {
        using var folder = new Folder();
        await using var store = await LabCatalog.CreateAsync(folder.Db);
        await InsertSyntheticAsync(folder.Db);
        var profiles = await store.ListProfilesAsync(10);
        Require(profiles.Count == 1 && profiles[0].Id == "synthetic", "Profile catalog mismatch");
        string readable = string.Join(",", profiles.Select(p => p.Label));
        Require(!readable.Contains("VIN", StringComparison.OrdinalIgnoreCase) &&
                !readable.Contains("PIN", StringComparison.OrdinalIgnoreCase),
            "Unexpected private field");
    }

    private static async Task Test05()
    {
        using var folder = new Folder();
        await using var store = await LabCatalog.CreateAsync(folder.Db);
        await InsertSyntheticAsync(folder.Db);
        ScenarioRevisionMetadata? record = await store.GetSealedRevisionAsync("scenario", 1);
        Require(record is not null && record.SnapshotSha256.Length == 64,
            "Sealed metadata missing");
        Require(!record!.SnapshotBytesVerified && !record.RuntimeApproved,
            "Metadata incorrectly enabled ECU responses");
        Require(await store.GetSealedRevisionAsync("scenario", 2) is null, "Invented revision");
    }

    private static async Task Test06()
    {
        using var folder = new Folder();
        await using (var store = await LabCatalog.CreateAsync(folder.Db))
        {
            await InsertSyntheticAsync(folder.Db);
            await store.BackupAsync(folder.Backup);
            await Fail<LabStorageException>(() => store.BackupAsync(folder.Backup));
        }
        await using var backup = await LabCatalog.OpenAsync(folder.Backup);
        Require((await backup.GetHealthAsync()).Profiles == 1, "WAL backup omitted committed rows");
    }

    private static async Task Test07()
    {
        using var folder = new Folder();
        await File.WriteAllBytesAsync(folder.Db, "not sqlite"u8.ToArray());
        await Fail<LabStorageException>(async () => { await using var _ = await LabCatalog.OpenAsync(folder.Db); });
        File.Delete(folder.Db);
        await using var store = await LabCatalog.CreateAsync(folder.Db);
        await Fail<ArgumentException>(async () => { await store.GetSealedRevisionAsync("';DROP TABLE", 1); });
        await Fail<ArgumentOutOfRangeException>(async () => { await store.ListProfilesAsync(101); });
    }

    private static Task Test09()
    {
        const long gib = 1024L * 1024 * 1024;
        Require(LabCatalog.FitsDatabaseBudget(10 * gib), "10 GiB target rejected");
        Require(LabCatalog.FitsDatabaseBudget(12 * gib), "12 GiB guard boundary rejected");
        Require(!LabCatalog.FitsDatabaseBudget(12 * gib + 1), "Oversized database accepted");
        Require(!LabCatalog.FitsDatabaseBudget(-1), "Negative database size accepted");
        return Task.CompletedTask;
    }

    private static async Task Test08()
    {
        using var folder = new Folder();
        using var cancelled = new CancellationTokenSource();
        cancelled.Cancel();
        await Fail<OperationCanceledException>(async () =>
        {
            await using var _ = await LabCatalog.CreateAsync(folder.Db, cancelled.Token);
        });
        Require(!File.Exists(folder.Db), "Cancellation created an unwanted database");
        var store = await LabCatalog.CreateAsync(folder.Db);
        try
        {
            var results = await Task.WhenAll(Enumerable.Range(0, 10)
                .Select(_ => store.GetHealthAsync()));
            Require(results.All(x => x.IntegrityOk), "Concurrent health failure");
        }
        finally { await store.DisposeAsync(); }
        await Fail<ObjectDisposedException>(async () => { await store.GetHealthAsync(); });
    }
}
