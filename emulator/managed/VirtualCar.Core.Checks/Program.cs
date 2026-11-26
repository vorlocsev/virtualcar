using System.Security.Cryptography;
using VirtualCar.Core;

namespace VirtualCar.Core.Checks;

internal static class Program
{
    private static async Task<int> Main()
    {
        (string Name, Func<Task> Test)[] checks =
        [
            ("01 No session before scenario activation", Test01),
            ("02 Only approved synthetic provenance", Test02),
            ("03 Hash verification and immutable payload copy", Test03),
            ("04 No scenario switching with live sessions", Test04),
            ("05 Reset and stale-generation rejection", Test05),
            ("06 Failed or cancelled preparation stays offline", Test06),
            ("07 Bounded concurrent session management", Test07),
            ("08 Shutdown remains invalid after stop fault", Test08)
        ];

        checks = [..checks, ..CemPreviewChecks.All, ..UiLanguageChecks.All, ..NativeEcmScenarioChecks.All, ..NativeEcmApplyChecks.All, ..NativeEcmRestoreChecks.All, ..NativeIgnitionChecks.All, ..NativeEcuInventoryChecks.All, ..NativeCanTraceChecks.All, ..NativeDiagnosticJournalChecks.All, ..AcceptanceReportChecks.All, ..AcceptanceBundleChecks.All];

        int passed = 0;
        foreach (var (name, test) in checks)
        {
            try
            {
                await test();
                passed++;
                Console.WriteLine("PASS " + name);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("FAIL " + name + " (" + ex.GetType().Name + ")");
            }
        }

        Console.WriteLine($"VirtualCar.Core synthetic checks: {passed}/{checks.Length}");
        return passed == checks.Length ? 0 : 1;
    }

    private static ScenarioCandidate Candidate(
        ScenarioProvenance source = ScenarioProvenance.Synthetic,
        bool approved = true,
        string? digest = null,
        byte[]? bytes = null)
    {
        bytes ??= [0x22, 0xF1, 0x90]; // Generic synthetic DID request, NOT a Volvo frame.
        return new ScenarioCandidate("synthetic-ecu-test", 1, source, approved,
            bytes, digest ?? Convert.ToHexString(SHA256.HashData(bytes)));
    }

    private static (ScenarioCoordinator Core, FakeCatalog Catalog, FakeRuntime Runtime)
        NewSystem(ScenarioCandidate? candidate = null)
    {
        var catalog = new FakeCatalog { Candidate = candidate ?? Candidate() };
        var runtime = new FakeRuntime();
        return (new ScenarioCoordinator(catalog, runtime), catalog, runtime);
    }

    private static void Require(bool condition, string reason)
    {
        if (!condition) throw new InvalidOperationException(reason);
    }

    private static async Task ExpectFailure<T>(Func<Task> action)
        where T : Exception
    {
        try { await action(); }
        catch (T) { return; }
        throw new InvalidOperationException("Expected " + typeof(T).Name);
    }

    private static async Task Test01()
    {
        var (core, _, runtime) = NewSystem();
        await ExpectFailure<InvalidOperationException>(async () => { await core.OpenSessionAsync(); });
        Require(runtime.PrepareCount == 0, "Unselected runtime was prepared");
        await core.SelectAsync("synthetic-ecu-test", 1);
        var token = await core.OpenSessionAsync();
        await core.ValidateSessionAsync(token);
        await core.CloseSessionAsync(token);
        await core.ShutdownAsync();
    }

    private static async Task Test02()
    {
        foreach (var (source, approved) in new[]
        {
            (ScenarioProvenance.ResearchOnly, true),
            (ScenarioProvenance.CapturedPrivate, true),
            (ScenarioProvenance.Synthetic, false)
        })
        {
            var (core, _, runtime) = NewSystem(Candidate(source, approved));
            await ExpectFailure<InvalidOperationException>(() => core.SelectAsync("synthetic-ecu-test", 1));
            Require(!await core.HasSelectedScenarioAsync(), "Rejected source was activated");
            Require(runtime.PrepareCount == 0, "Rejected source reached the runtime");
        }
    }

    private static async Task Test03()
    {
        byte[] bytes = [0x22, 0xF1, 0x90];
        var (core, catalog, runtime) = NewSystem(Candidate(bytes: bytes));
        await core.SelectAsync("synthetic-ecu-test", 1);
        Require(runtime.LastPrepared is not null, "Scenario not prepared");
        bytes[0] = 0xFF;
        Require(runtime.LastPrepared!.CanonicalBytes[0] == 0x22, "Mutable catalog buffer escaped");

        await core.ResetAsync();
        catalog.Candidate = Candidate(digest: new string('0', 64));
        await ExpectFailure<InvalidOperationException>(() => core.SelectAsync("synthetic-ecu-test", 1));
        Require(!await core.HasSelectedScenarioAsync(), "Corrupt hash left runtime active");
    }

    private static async Task Test04()
    {
        var (core, _, runtime) = NewSystem();
        await core.SelectAsync("synthetic-ecu-test", 1);
        var token = await core.OpenSessionAsync();
        int before = runtime.PrepareCount;
        await ExpectFailure<InvalidOperationException>(() => core.SelectAsync("synthetic-ecu-test", 1));
        Require(runtime.PrepareCount == before, "Switched during live session");
        await core.ValidateSessionAsync(token);
        await core.CloseSessionAsync(token);
    }

    private static async Task Test05()
    {
        var (core, _, _) = NewSystem();
        await core.SelectAsync("synthetic-ecu-test", 1);
        var old = await core.OpenSessionAsync();
        await ExpectFailure<InvalidOperationException>(() => core.ResetAsync());
        await core.CloseSessionAsync(old);
        await core.ResetAsync();
        await ExpectFailure<InvalidOperationException>(() => core.ValidateSessionAsync(old));
        var newer = await core.OpenSessionAsync();
        Require(newer.Generation != old.Generation, "Reset did not increment generation");
    }

    private static async Task Test06()
    {
        var (core, _, runtime) = NewSystem();
        runtime.FailPrepare = true;
        await ExpectFailure<InvalidOperationException>(() => core.SelectAsync("synthetic-ecu-test", 1));
        Require(!await core.HasSelectedScenarioAsync(), "Failed preparation leaked selection");

        runtime.FailPrepare = false;
        using var cancel = new CancellationTokenSource();
        cancel.Cancel();
        await ExpectFailure<OperationCanceledException>(() =>
            core.SelectAsync("synthetic-ecu-test", 1, cancel.Token));
        Require(!await core.HasSelectedScenarioAsync(), "Cancellation activated scenario");
    }

    private static async Task Test07()
    {
        var (core, _, _) = NewSystem();
        await core.SelectAsync("synthetic-ecu-test", 1);
        SessionToken[] sessions = await Task.WhenAll(
            Enumerable.Range(0, ScenarioCoordinator.MaximumSessions)
                .Select(_ => core.OpenSessionAsync()));
        Require(sessions.Select(x => x.Id).Distinct().Count() == ScenarioCoordinator.MaximumSessions,
            "Duplicate session IDs");
        await ExpectFailure<InvalidOperationException>(async () => await core.OpenSessionAsync());
        await Task.WhenAll(sessions.Select(session => core.CloseSessionAsync(session)));
        await core.ResetAsync();
    }

    private static async Task Test08()
    {
        var (core, _, runtime) = NewSystem();
        await core.SelectAsync("synthetic-ecu-test", 1);
        var token = await core.OpenSessionAsync();
        runtime.FailStop = true;
        await ExpectFailure<InvalidOperationException>(() => core.ShutdownAsync());
        Require(!await core.HasSelectedScenarioAsync(), "Shutdown fault retained scenario");
        await ExpectFailure<ObjectDisposedException>(() => core.ValidateSessionAsync(token));
        await ExpectFailure<ObjectDisposedException>(async () => await core.OpenSessionAsync());
    }

    private sealed class FakeCatalog : IScenarioCatalog
    {
        public ScenarioCandidate? Candidate { get; set; }

        public Task<ScenarioCandidate?> LoadAsync(
            string id, long revision, CancellationToken cancellationToken) =>
            Task.FromResult(Candidate);
    }

    private sealed class FakeRuntime : IScenarioRuntime
    {
        public int PrepareCount { get; private set; }
        public ScenarioSnapshot? LastPrepared { get; private set; }
        public bool FailPrepare { get; set; }
        public bool FailStop { get; set; }

        public Task PrepareAsync(ScenarioSnapshot snapshot, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (FailPrepare) throw new InvalidOperationException("Synthetic prepare failure");
            PrepareCount++;
            LastPrepared = snapshot;
            return Task.CompletedTask;
        }

        public Task StopAsync(CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (FailStop) throw new InvalidOperationException("Synthetic stop failure");
            LastPrepared = null;
            return Task.CompletedTask;
        }
    }
}
