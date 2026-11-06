using Microsoft.Data.Sqlite;
using VirtualCar.Storage;

var tests = new (string Name, Func<Task> Run)[]
{
    ("1. Explicit first-time migration", CreateAndReopen),
    ("2. Reject overwrite", NoOverwrite),
    ("3. Corruption and tampered schema", CorruptionAndSchema),
    ("4. Synthetic-only profile persistence", SyntheticProfile),
    ("5. Validate user selectors and SQL boundaries", RejectInputs),
    ("6. Sealed metadata is never runtime authority", MetadataOnly),
    ("7. Online WAL backup and no replacement", Backup),
    ("8. Cancellation, FK enforcement, disposal", CancellationAndFk)
};
foreach (var (name, check) in tests)
{
    await check();
    Console.WriteLine("PASS " + name);
}
Console.WriteLine("8/8 C# SQLite test groups passed. No vehicle or J2534 tested.");

static string DirectoryForTest()
{
    string path = Path.Combine(Path.GetTempPath(), "vcar-sqlite-" + Guid.NewGuid().ToString("N"));
    Directory.CreateDirectory(path);
    return path;
}
static async Task InNewDb(Func<LabStorage, string, Task> check)
{
    string folder = DirectoryForTest();
    try
    {
        using var db = LabStorage.Open(Path.Combine(folder, "lab.db"), initialize: true);
        await check(db, folder);
    }
    finally { Directory.Delete(folder, recursive: true); }
}
static void Ensure(bool condition, string why)
{
    if (!condition) throw new Exception(why);
}
static async Task MustFail(Func<Task> action)
{
    try { await action(); }
    catch (LabStorageException) { return; }
    throw new Exception("Operation should have been rejected.");
}
static async Task CreateAndReopen()
{
    await InNewDb(async (db, dir) =>
    {
        Ensure((await db.ListProfilesAsync()).Count == 0, "Fresh DB not empty");
        using var separate = new SqliteConnection(new SqliteConnectionStringBuilder {
            DataSource = Path.Combine(dir, "lab.db"), Mode = SqliteOpenMode.ReadWrite, ForeignKeys = true
        }.ToString());
        separate.Open();
        using var cmd = separate.CreateCommand();
        cmd.CommandText = "SELECT version,length(checksum_sha256) FROM schema_migrations";
        using var reader = cmd.ExecuteReader();
        Ensure(reader.Read() && reader.GetInt32(0) == 1 && reader.GetInt32(1) == 64, "Migration missing");
        using var reopened = LabStorage.Open(Path.Combine(dir, "lab.db"));
        Ensure((await reopened.ListProfilesAsync()).Count == 0, "Reopen changed schema");
    });
}
static async Task NoOverwrite()
{
    await InNewDb(async (_, dir) =>
    {
        string dbPath = Path.Combine(dir, "lab.db");
        byte[] first = File.ReadAllBytes(dbPath);
        await MustFail(() => Task.Run(() => LabStorage.Open(dbPath, initialize: true).Dispose()));
        Ensure(first.SequenceEqual(File.ReadAllBytes(dbPath)), "Reinitialize overwrote original DB");
    });
}
static async Task CorruptionAndSchema()
{
    string dir = DirectoryForTest();
    try
    {
        string path = Path.Combine(dir, "lab.db");
        File.WriteAllText(path, "synthetic-non-sqlite");
        await MustFail(() => Task.Run(() => LabStorage.Open(path).Dispose()));
        File.Delete(path);
        using (var db = LabStorage.Open(path, initialize: true)) { }
        using (var edit = new SqliteConnection(new SqliteConnectionStringBuilder {
            DataSource = path, Mode = SqliteOpenMode.ReadWrite
        }.ToString()))
        {
            edit.Open();
            using var cmd = edit.CreateCommand();
            cmd.CommandText = "UPDATE schema_migrations SET checksum_sha256=lower(hex(randomblob(32)))";
            cmd.ExecuteNonQuery();
        }
        await MustFail(() => Task.Run(() => LabStorage.Open(path).Dispose()));
    }
    finally { Directory.Delete(dir, true); }
}
static async Task SyntheticProfile()
{
    await InNewDb(async (db, _) =>
    {
        await db.AddSyntheticProfileAsync("lab_car", "Synthetic vehicle", "GENERIC", 2009);
        var list = await db.ListProfilesAsync(10);
        Ensure(list.Count == 1 && list[0].Provenance == "synthetic", "Profile origin wrong");
        Ensure(list[0].Id == "lab_car" && list[0].ModelYear == 2009, "Roundtrip mismatch");
        Ensure(list[0].Label == "Synthetic vehicle", "Profile label wrong");
    });
}
static async Task RejectInputs()
{
    await InNewDb(async (db, _) =>
    {
        await MustFail(() => db.AddSyntheticProfileAsync("';drop", "Bad", "GENERIC", 2009));
        await MustFail(() => db.AddSyntheticProfileAsync("lab", new string('x', 200), "GENERIC", 2009));
        await MustFail(() => db.ListProfilesAsync(101));
        await MustFail(() => db.ReadSealedMetadataAsync("x' OR 1=1--", 1));
        Ensure((await db.ListProfilesAsync()).Count == 0, "Invalid input reached database");
    });
}
static async Task MetadataOnly()
{
    await InNewDb(async (db, dir) =>
    {
        await db.AddSyntheticProfileAsync("lab", "Synthetic vehicle", "GENERIC", 2009);
        using (var sql = new SqliteConnection(new SqliteConnectionStringBuilder {
            DataSource = Path.Combine(dir, "lab.db"), Mode = SqliteOpenMode.ReadWrite, ForeignKeys = true
        }.ToString()))
        {
            sql.Open();
            using var cmd = sql.CreateCommand();
            cmd.CommandText = @"INSERT INTO scenarios VALUES('demo','Synthetic scenario','lab','2026-11-06T00:00:00Z');
INSERT INTO scenario_revisions VALUES('r1','demo',1,1,$hash,'2026-11-06T00:00:00Z');";
            cmd.Parameters.AddWithValue("$hash", new string('a', 64));
            cmd.ExecuteNonQuery();
        }
        var read = await db.ReadSealedMetadataAsync("demo", 1);
        if (read is null) throw new Exception("Missing sealed metadata");
        Ensure(read.Id == "r1", "Unexpected scenario revision");
        Ensure(!read.SnapshotBytesVerified && !read.RuntimeSelected && !read.PhysicalVehicleVerified,
            "SQL digest falsely authorized an ECU scenario");
    });
}
static async Task Backup()
{
    await InNewDb(async (db, dir) =>
    {
        await db.AddSyntheticProfileAsync("lab", "Synthetic vehicle", "GENERIC", 2009);
        string backup = Path.Combine(dir, "backup.db");
        db.BackupTo(backup);
        using var restored = LabStorage.Open(backup);
        Ensure((await restored.ListProfilesAsync()).Count == 1, "Online backup dropped rows");
        await MustFail(() => Task.Run(() => db.BackupTo(backup)));
    });
}
static async Task CancellationAndFk()
{
    await InNewDb(async (db, dir) =>
    {
        using var cts = new CancellationTokenSource();
        cts.Cancel();
        try { await db.ListProfilesAsync(ct: cts.Token); throw new Exception("Cancelled read succeeded"); }
        catch (OperationCanceledException) { }
        using (var external = new SqliteConnection(new SqliteConnectionStringBuilder {
            DataSource = Path.Combine(dir, "lab.db"), Mode = SqliteOpenMode.ReadWrite, ForeignKeys = true
        }.ToString()))
        {
            external.Open();
            using var cmd = external.CreateCommand();
            cmd.CommandText = "INSERT INTO can_buses VALUES('bus','missing','HS',500000,'11bit')";
            try { cmd.ExecuteNonQuery(); throw new Exception("Orphan CAN bus inserted"); }
            catch (SqliteException) { }
        }
        db.Dispose();
        try { await db.ListProfilesAsync(); throw new Exception("Disposed DB remained accessible"); }
        catch (ObjectDisposedException) { }
    });
}
