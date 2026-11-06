using System.Security.Cryptography;
using VirtualCar.Core;

var tests = new (string Name, Func<Task> Run)[]
{
    ("1. Verified immutable synthetic snapshot", ValidSnapshot),
    ("2. Bad digest or empty bytes fail closed", InvalidHash),
    ("3. Research and unapproved fixtures forbidden", Unapproved),
    ("4. Live J2534 session blocks scenario mutation", SessionBlocksMutation),
    ("5. Reset changes session generation", ResetAfterSession),
    ("6. Limit concurrent laboratory sessions", SessionLimit),
    ("7. Cancellation and runtime fault invalidate selection", CancellationAndFault),
    ("8. Dispose invalidates state", DisposeInvalidates)
};

foreach (var (name, run) in tests)
{
    await run();
    Console.WriteLine("PASS " + name);
}
Console.WriteLine("8/8 synthetic C# lifecycle gates passed. No native J2534 or physical ECU used.");

static ScenarioSource Sample(byte[]? data = null, bool approved = true,
    ScenarioOrigin origin = ScenarioOrigin.Synthetic, string? sha = null)
{
    data ??= "GENERIC-SYNTHETIC-READONLY"u8.ToArray();
    return new ScenarioSource("lab-synthetic", 1, sha ?? Convert.ToHexString(SHA256.HashData(data)),
        origin, approved, data);
}

static (LabController Core, TestCatalog Catalog, TestRuntime Runtime) Build(ScenarioSource? source = null)
{
    var catalog = new TestCatalog { Snapshot = source ?? Sample() };
    var runtime = new TestRuntime();
    return (new LabController(catalog, runtime), catalog, runtime);
}

static async Task ExpectFailure(Func<Task> work)
{
    try { await work(); }
    catch (LabException) { return; }
    throw new Exception("Expected a laboratory guard failure.");
}

static async Task ValidSnapshot()
{
    byte[] data = "GENERIC-SYNTHETIC-READONLY"u8.ToArray();
    var (core, _, runtime) = Build(Sample(data));
    await using (core)
    {
        await core.SelectAsync("lab-synthetic", 1);
        data[0] = 0;
        var current = await core.GetCurrentAsync() ?? throw new Exception("No scenario selected");
        Check(current.ExportSnapshotCopy()[0] == (byte)'G', "Source mutation changed snapshot");
        byte[] received = current.ExportSnapshotCopy();
        received[0] = 0;
        Check(current.ExportSnapshotCopy()[0] == (byte)'G', "Snapshot escaped by reference");
        Check(runtime.Prepared == 1 && runtime.Stopped >= 1, "Lifecycle not invoked");
    }
}

static async Task InvalidHash()
{
    var (core, _, _) = Build(Sample(sha: new string('0', 64)));
    await using (core)
    {
        await ExpectFailure(() => core.SelectAsync("lab-synthetic", 1));
        Check(await core.GetCurrentAsync() is null, "Mismatched hash was selected");
    }
    var (empty, _, _) = Build(Sample(data: Array.Empty<byte>()));
    await using (empty)
        await ExpectFailure(() => empty.SelectAsync("lab-synthetic", 1));
}

static async Task Unapproved()
{
    var (a, _, _) = Build(Sample(approved: false));
    await using (a)
        await ExpectFailure(() => a.SelectAsync("lab-synthetic", 1));
    var (b, _, _) = Build(Sample(origin: ScenarioOrigin.ResearchOnly));
    await using (b)
        await ExpectFailure(() => b.SelectAsync("lab-synthetic", 1));
}

static async Task SessionBlocksMutation()
{
    var (core, _, _) = Build();
    await using (core)
    {
        await core.SelectAsync("lab-synthetic", 1);
        var token = await core.OpenSessionAsync();
        await core.ValidateSessionAsync(token);
        await ExpectFailure(() => core.SelectAsync("lab-synthetic", 1));
        await ExpectFailure(() => core.ResetAsync());
        await core.CloseSessionAsync(token);
        await ExpectFailure(() => core.ValidateSessionAsync(token));
    }
}

static async Task ResetAfterSession()
{
    var (core, _, _) = Build();
    await using (core)
    {
        await core.SelectAsync("lab-synthetic", 1);
        var old = await core.OpenSessionAsync();
        await core.CloseSessionAsync(old);
        await core.ResetAsync();
        await ExpectFailure(() => core.ValidateSessionAsync(old));
        var next = await core.OpenSessionAsync();
        Check(next.Generation != old.Generation, "Reset retained stale generation");
        await core.CloseSessionAsync(next);
    }
}

static async Task SessionLimit()
{
    var (core, _, _) = Build();
    await using (core)
    {
        await core.SelectAsync("lab-synthetic", 1);
        var tasks = Enumerable.Range(0, LabController.MaxSessions)
            .Select(_ => core.OpenSessionAsync()).ToArray();
        var tokens = await Task.WhenAll(tasks);
        Check(tokens.Select(t => t.Id).Distinct().Count() == LabController.MaxSessions, "Duplicate ID");
        await ExpectFailure(async () => { _ = await core.OpenSessionAsync(); });
        foreach (var t in tokens) await core.CloseSessionAsync(t);
    }
}

static async Task CancellationAndFault()
{
    var (cancelled, _, _) = Build();
    await using (cancelled)
    {
        using var cts = new CancellationTokenSource();
        cts.Cancel();
        try { await cancelled.SelectAsync("lab-synthetic", 1, cts.Token); }
        catch (OperationCanceledException) { /* expected */ }
        Check(await cancelled.GetCurrentAsync() is null, "Cancelled select mutated state");
    }
    var (fault, _, runtime) = Build();
    await using (fault)
    {
        await fault.SelectAsync("lab-synthetic", 1);
        runtime.FailPrepare = true;
        try { await fault.SelectAsync("lab-synthetic", 1); }
        catch (InvalidOperationException) { /* expected */ }
        Check(await fault.GetCurrentAsync() is null, "Failed prepare retained prior selection");
    }
}

static async Task DisposeInvalidates()
{
    var (core, _, _) = Build();
    await core.SelectAsync("lab-synthetic", 1);
    var token = await core.OpenSessionAsync();
    await core.DisposeAsync();
    try
    {
        await core.ValidateSessionAsync(token);
        throw new Exception("Disposed controller accepted a session");
    }
    catch (ObjectDisposedException) { /* expected */ }
}

static void Check(bool condition, string message)
{
    if (!condition) throw new Exception(message);
}

file sealed class TestCatalog : IScenarioCatalog
{
    public ScenarioSource? Snapshot { get; init; }
    public Task<ScenarioSource?> LoadMaterializedAsync(string id, int revision, CancellationToken ct)
    {
        ct.ThrowIfCancellationRequested();
        return Task.FromResult(Snapshot);
    }
}

file sealed class TestRuntime : IScenarioRuntime
{
    public int Prepared { get; private set; }
    public int Stopped { get; private set; }
    public bool FailPrepare { get; set; }

    public Task PrepareAsync(VerifiedScenario scenario, CancellationToken ct)
    {
        ct.ThrowIfCancellationRequested();
        if (FailPrepare) throw new InvalidOperationException("Synthetic preparation failure");
        Prepared++;
        return Task.CompletedTask;
    }

    public Task StopAsync(CancellationToken ct)
    {
        Stopped++;
        return Task.CompletedTask;
    }
}
